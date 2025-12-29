"""
Temporal client - for starting workflows from the FastAPI application.
"""

import logging
from typing import Dict, Any, Optional
from temporalio.client import Client

from app.core.config import settings

logger = logging.getLogger(__name__)


class TemporalClient:
    """Client for interacting with Temporal workflows."""

    def __init__(self):
        """Initialize Temporal client."""
        self._client: Optional[Client] = None

    async def connect(self):
        """Connect to Temporal server."""
        if self._client is None:
            temporal_address = f"{settings.TEMPORAL_HOST}:{settings.TEMPORAL_PORT}"
            logger.info(f"Connecting to Temporal at {temporal_address}")

            self._client = await Client.connect(
                temporal_address,
                namespace=settings.TEMPORAL_NAMESPACE,
            )

            logger.info(f"Connected to Temporal namespace: {settings.TEMPORAL_NAMESPACE}")

    async def start_document_processing(
        self,
        document_id: int,
        minio_key: str,
        document_type: str
    ) -> Dict[str, str]:
        """
        Start a document processing workflow.

        Args:
            document_id: Database ID of the document
            minio_key: MinIO object key
            document_type: Type of document (pv_ag, diagnostic, etc.)

        Returns:
            Dict with workflow_id and workflow_run_id
        """
        await self.connect()

        workflow_id = f"document-processing-{document_id}"

        logger.info(f"Starting document processing workflow: {workflow_id}")

        handle = await self._client.start_workflow(
            "DocumentProcessingWorkflow",
            args=[document_id, minio_key, document_type],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )

        logger.info(f"Workflow started: {handle.id}, run_id: {handle.result_run_id}")

        return {
            "workflow_id": handle.id,
            "workflow_run_id": handle.result_run_id,
        }

    async def start_document_aggregation(
        self,
        property_id: int,
        category: str,
        document_ids: list[int]
    ) -> Dict[str, str]:
        """
        Start a document aggregation workflow.

        Args:
            property_id: Database ID of the property
            category: Document category
            document_ids: List of document IDs to aggregate

        Returns:
            Dict with workflow_id and workflow_run_id
        """
        await self.connect()

        workflow_id = f"document-aggregation-{property_id}-{category}"

        logger.info(f"Starting document aggregation workflow: {workflow_id}")

        handle = await self._client.start_workflow(
            "DocumentAggregationWorkflow",
            args=[property_id, category, document_ids],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )

        logger.info(f"Workflow started: {handle.id}, run_id: {handle.result_run_id}")

        return {
            "workflow_id": handle.id,
            "workflow_run_id": handle.result_run_id,
        }

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get the status of a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Dict with workflow status
        """
        await self.connect()

        handle = self._client.get_workflow_handle(workflow_id)

        try:
            result = await handle.result()
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "result": result,
            }
        except Exception as e:
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(e),
            }


# Singleton instance
_temporal_client: Optional[TemporalClient] = None


def get_temporal_client() -> TemporalClient:
    """Get or create Temporal client singleton."""
    global _temporal_client
    if _temporal_client is None:
        _temporal_client = TemporalClient()
    return _temporal_client
