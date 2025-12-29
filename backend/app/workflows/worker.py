"""
Temporal worker - runs activities and workflows.
This should be run as a separate process (temporal-worker service in docker-compose).
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker

from app.core.config import settings
from app.workflows.document_workflows import DocumentProcessingWorkflow, DocumentAggregationWorkflow
from app.workflows.activities import (
    download_from_minio,
    pdf_to_images,
    analyze_with_langchain,
    update_document_status,
    save_analysis_results,
    calculate_file_hash,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Start the Temporal worker."""
    # Connect to Temporal server
    temporal_address = f"{settings.TEMPORAL_HOST}:{settings.TEMPORAL_PORT}"
    logger.info(f"Connecting to Temporal at {temporal_address}")

    client = await Client.connect(
        temporal_address,
        namespace=settings.TEMPORAL_NAMESPACE,
    )

    logger.info(f"Connected to Temporal namespace: {settings.TEMPORAL_NAMESPACE}")

    # Create worker
    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[DocumentProcessingWorkflow, DocumentAggregationWorkflow],
        activities=[
            download_from_minio,
            pdf_to_images,
            analyze_with_langchain,
            update_document_status,
            save_analysis_results,
            calculate_file_hash,
        ],
    )

    logger.info(f"Starting worker on task queue: {settings.TEMPORAL_TASK_QUEUE}")
    logger.info("Worker is ready to process workflows and activities")

    # Run worker
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
