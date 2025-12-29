"""
Webhook endpoints for external services.
Includes MinIO bucket notifications for triggering document processing.
"""

import logging
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.workflows.client import get_temporal_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/minio")
async def minio_webhook(request: Request) -> Dict[str, str]:
    """
    Handle MinIO bucket notifications.

    When a file is uploaded to MinIO, this webhook is triggered.
    It starts a Temporal workflow to process the document.

    MinIO webhook payload structure:
    {
      "EventName": "s3:ObjectCreated:Put",
      "Key": "documents/123/file.pdf",
      "Records": [...]
    }
    """
    try:
        payload = await request.json()
        logger.info(f"Received MinIO webhook: {payload.get('EventName')}")

        # Extract object key from payload
        records = payload.get("Records", [])
        if not records:
            logger.warning("No records in MinIO webhook payload")
            return {"status": "ignored", "reason": "no_records"}

        for record in records:
            event_name = record.get("eventName", "")
            s3_info = record.get("s3", {})
            object_info = s3_info.get("object", {})
            object_key = object_info.get("key", "")

            # Only process ObjectCreated events
            if not event_name.startswith("s3:ObjectCreated"):
                logger.info(f"Ignoring event: {event_name}")
                continue

            logger.info(f"Processing object: {object_key}")

            # Extract document ID from object key
            # Expected format: documents/{document_id}/{filename}
            parts = object_key.split("/")
            if len(parts) < 2 or parts[0] != "documents":
                logger.warning(f"Invalid object key format: {object_key}")
                continue

            try:
                document_id = int(parts[1])
            except ValueError:
                logger.warning(f"Could not parse document ID from key: {object_key}")
                continue

            # Get document from database
            db = SessionLocal()
            try:
                document = db.query(Document).filter(Document.id == document_id).first()
                if not document:
                    logger.warning(f"Document {document_id} not found")
                    continue

                # Check if workflows are enabled
                if not settings.ENABLE_TEMPORAL_WORKFLOWS:
                    logger.info("Temporal workflows disabled, skipping workflow start")
                    continue

                # Determine document type
                document_type = document.document_category or "diagnostic"
                if document.document_subcategory:
                    document_type = document.document_subcategory

                # Start Temporal workflow
                temporal_client = get_temporal_client()
                workflow_info = await temporal_client.start_document_processing(
                    document_id=document_id,
                    minio_key=object_key,
                    document_type=document_type
                )

                # Update document with workflow info
                document.workflow_id = workflow_info["workflow_id"]
                document.workflow_run_id = workflow_info["workflow_run_id"]
                document.processing_status = "pending"
                db.commit()

                logger.info(
                    f"Started workflow {workflow_info['workflow_id']} for document {document_id}"
                )

            finally:
                db.close()

        return {"status": "success", "message": "Webhooks processed"}

    except Exception as e:
        logger.error(f"Error processing MinIO webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def webhook_health() -> Dict[str, str]:
    """Health check endpoint for webhooks."""
    return {"status": "healthy"}
