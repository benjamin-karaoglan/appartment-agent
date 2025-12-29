"""
Temporal workflows for document processing.
Workflows orchestrate activities and define the processing logic.
"""

import logging
from datetime import timedelta
from typing import Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities
with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        download_from_minio,
        pdf_to_images,
        analyze_with_langchain,
        update_document_status,
        save_analysis_results,
        calculate_file_hash,
    )

logger = logging.getLogger(__name__)


@workflow.defn(name="DocumentProcessingWorkflow")
class DocumentProcessingWorkflow:
    """
    Workflow for processing a single document.

    Steps:
    1. Download document from MinIO
    2. Convert PDF to images
    3. Analyze with LangChain + Claude vision
    4. Save results to database
    5. Update status
    """

    @workflow.run
    async def run(self, document_id: int, minio_key: str, document_type: str) -> Dict[str, Any]:
        """
        Run the document processing workflow.

        Args:
            document_id: Database ID of the document
            minio_key: MinIO object key
            document_type: Type of document (pv_ag, diagnostic, etc.)

        Returns:
            Dict with processing results
        """
        workflow.logger.info(f"Starting document processing workflow for document {document_id}")

        # Define retry policy for activities
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=60),
            maximum_attempts=3,
            backoff_coefficient=2.0,
        )

        try:
            # Step 1: Update status to processing
            await workflow.execute_activity(
                update_document_status,
                args=[document_id, "processing", None],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # Step 2: Download from MinIO
            file_data = await workflow.execute_activity(
                download_from_minio,
                args=[minio_key],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )

            # Step 3: Calculate file hash (for deduplication tracking)
            file_hash = await workflow.execute_activity(
                calculate_file_hash,
                args=[file_data],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # Step 4: Convert PDF to images
            images_base64 = await workflow.execute_activity(
                pdf_to_images,
                args=[file_data],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=retry_policy,
            )

            # Step 5: Analyze with LangChain
            analysis_result = await workflow.execute_activity(
                analyze_with_langchain,
                args=[images_base64, document_id, document_type],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=retry_policy,
            )

            # Step 6: Save results
            await workflow.execute_activity(
                save_analysis_results,
                args=[document_id, analysis_result],
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=retry_policy,
            )

            # Step 7: Update status to completed
            await workflow.execute_activity(
                update_document_status,
                args=[document_id, "completed", None],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            workflow.logger.info(f"Document processing workflow completed for document {document_id}")

            return {
                "document_id": document_id,
                "status": "completed",
                "file_hash": file_hash,
                "pages_processed": len(images_base64),
                "tokens_used": analysis_result.get("tokens_used", 0),
                "estimated_cost": analysis_result.get("estimated_cost", 0.0),
            }

        except Exception as e:
            workflow.logger.error(f"Document processing workflow failed for document {document_id}: {e}")

            # Update status to failed
            await workflow.execute_activity(
                update_document_status,
                args=[document_id, "failed", str(e)],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            return {
                "document_id": document_id,
                "status": "failed",
                "error": str(e),
            }


@workflow.defn(name="DocumentAggregationWorkflow")
class DocumentAggregationWorkflow:
    """
    Workflow for aggregating multiple documents of the same category.

    This workflow is triggered after multiple documents are processed
    to create a combined summary (e.g., all PV d'AG for a property).
    """

    @workflow.run
    async def run(self, property_id: int, category: str, document_ids: list[int]) -> Dict[str, Any]:
        """
        Run the document aggregation workflow.

        Args:
            property_id: Database ID of the property
            category: Document category (pv_ag, diagnostic, etc.)
            document_ids: List of document IDs to aggregate

        Returns:
            Dict with aggregation results
        """
        workflow.logger.info(
            f"Starting document aggregation workflow for property {property_id}, "
            f"category {category}, {len(document_ids)} documents"
        )

        # TODO: Implement aggregation workflow
        # This would:
        # 1. Fetch all document summaries from database
        # 2. Use LangChain to create aggregated summary
        # 3. Save to DocumentSummary table

        # For now, return placeholder
        return {
            "property_id": property_id,
            "category": category,
            "num_documents": len(document_ids),
            "status": "completed",
        }
