"""
Bulk Processor - Async document processing orchestrator.

Handles bulk document uploads with parallel processing and synthesis.
"""

import asyncio
import base64
import json
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.document import Document, DocumentSummary
from app.models.user import User
from app.services.ai.document_processor import get_document_processor
from app.services.storage import get_storage_service

logger = logging.getLogger(__name__)


def pdf_bytes_to_images_base64(pdf_bytes: bytes, max_pages: int = 20) -> List[str]:
    """Convert PDF bytes to base64-encoded images."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []

        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72))
            img_bytes = pix.tobytes("png")
            images.append(base64.b64encode(img_bytes).decode("utf-8"))

        doc.close()
        logger.info(f"Converted {len(images)} pages to images")
        return images

    except Exception as e:
        logger.error(f"PDF conversion error: {e}")
        return []


class BulkProcessor:
    """
    Orchestrates async bulk document processing.

    Flow:
    1. Download files from storage
    2. Convert PDFs to images
    3. Process each document with AI
    4. Save results incrementally
    5. Synthesize all results
    """

    def __init__(self):
        self.active_tasks: Dict[str, threading.Thread] = {}

    async def process_bulk_upload(
        self,
        workflow_id: str,
        property_id: int,
        document_uploads: List[Dict[str, Any]],
        output_language: str = "French",
    ) -> None:
        """Process bulk document upload asynchronously."""
        logger.info(f"Starting bulk processing: {workflow_id}, {len(document_uploads)} documents")

        db = SessionLocal()
        try:
            # Update all documents to processing status
            for upload in document_uploads:
                doc = db.query(Document).filter(Document.id == upload["document_id"]).first()
                if doc:
                    doc.processing_status = "processing"
            db.commit()

            # Step 1: Download files
            logger.info("Downloading files from storage...")
            file_data_list = await self._download_files(document_uploads)

            # Step 2: Convert PDFs to images
            logger.info("Converting PDFs to images...")
            images_list = await self._convert_pdfs(file_data_list)

            # Step 3: Process each document
            logger.info(f"Processing {len(document_uploads)} documents...")
            processor = get_document_processor()

            results = []
            for i, upload in enumerate(document_uploads):
                logger.info(f"Processing {i+1}/{len(document_uploads)}: {upload['filename']}")

                result = await processor.process_document(
                    {
                        "filename": upload["filename"],
                        "file_data_base64": images_list[i],
                        "document_id": upload["document_id"],
                    },
                    output_language=output_language,
                )
                results.append(result)

                # Save immediately
                await self._save_document_result(db, result)
                logger.info(f"Completed {i+1}/{len(document_uploads)}: {upload['filename']}")

            # Step 4: Synthesize
            logger.info("Synthesizing results...")
            synthesis = await processor.synthesize_results(results, output_language=output_language)

            # Step 5: Save synthesis
            await self._save_synthesis(db, synthesis, property_id)

            logger.info(f"Bulk processing completed: {workflow_id}")

        except Exception as e:
            logger.error(f"Bulk processing failed: {e}", exc_info=True)
            for upload in document_uploads:
                doc = db.query(Document).filter(Document.id == upload["document_id"]).first()
                if doc:
                    doc.processing_status = "failed"
                    doc.processing_error = str(e)
            db.commit()

        finally:
            db.close()
            if workflow_id in self.active_tasks:
                del self.active_tasks[workflow_id]

    async def _download_files(self, document_uploads: List[Dict[str, Any]]) -> List[bytes]:
        """Download files from storage in parallel."""
        storage = get_storage_service()

        async def download_one(minio_key: str) -> bytes:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, storage.download_file, minio_key)

        tasks = [download_one(upload["storage_key"]) for upload in document_uploads]
        return await asyncio.gather(*tasks)

    async def _convert_pdfs(self, file_data_list: List[bytes]) -> List[List[str]]:
        """Convert PDFs to images in parallel."""

        async def convert_one(file_data: bytes) -> List[str]:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, pdf_bytes_to_images_base64, file_data)

        tasks = [convert_one(data) for data in file_data_list]
        return await asyncio.gather(*tasks)

    async def _save_document_result(self, db: Session, result: Dict[str, Any]) -> None:
        """Save a processed document result."""
        doc_id = result.get("document_id")
        if not doc_id:
            return

        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return

        analysis = result.get("result", {})
        doc.document_category = result.get("document_type", "unknown")
        doc.document_subcategory = analysis.get("subcategory")
        doc.is_analyzed = True
        doc.analysis_summary = analysis.get("summary")
        doc.key_insights = analysis.get("key_insights", [])
        doc.estimated_annual_cost = analysis.get("estimated_annual_cost", 0.0)

        one_time = analysis.get("one_time_costs", 0.0)
        if isinstance(one_time, (int, float)):
            doc.one_time_costs = (
                [{"amount": one_time, "description": "Total"}] if one_time > 0 else []
            )
        else:
            doc.one_time_costs = one_time

        doc.processing_status = "completed"
        doc.parsed_at = datetime.utcnow()

        # Increment user's documents analyzed count
        if doc.user_id:
            user = db.query(User).filter(User.id == doc.user_id).first()
            if user:
                user.documents_analyzed_count = (user.documents_analyzed_count or 0) + 1

        db.commit()
        logger.info(f"Saved document {doc_id}: {result.get('filename')}")

    async def _save_synthesis(
        self, db: Session, synthesis: Dict[str, Any], property_id: int
    ) -> None:
        """Save synthesis to database."""
        summary = (
            db.query(DocumentSummary)
            .filter(DocumentSummary.property_id == property_id, DocumentSummary.category == None)
            .first()
        )

        if not summary:
            summary = DocumentSummary(property_id=property_id)
            db.add(summary)

        summary.overall_summary = synthesis.get("summary", "")
        summary.total_annual_cost = synthesis.get("total_annual_costs", 0.0)
        summary.total_one_time_cost = synthesis.get("total_one_time_costs", 0.0)
        summary.risk_level = synthesis.get("risk_level", "unknown")
        summary.key_findings = synthesis.get("key_findings", [])
        summary.recommendations = synthesis.get("recommendations", [])
        summary.synthesis_data = json.dumps(synthesis)
        summary.last_updated = datetime.utcnow()

        db.commit()
        logger.info(f"Saved synthesis for property {property_id}")

    def start_background_task(
        self,
        workflow_id: str,
        property_id: int,
        document_uploads: List[Dict[str, Any]],
        output_language: str = "French",
    ) -> None:
        """Start background processing in a dedicated thread."""

        def run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.process_bulk_upload(
                        workflow_id, property_id, document_uploads, output_language
                    )
                )
            finally:
                loop.close()

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        self.active_tasks[workflow_id] = thread
        logger.info(f"Started background thread for: {workflow_id}")


# Singleton
_instance: Optional[BulkProcessor] = None


def get_bulk_processor() -> BulkProcessor:
    """Get or create the BulkProcessor singleton."""
    global _instance
    if _instance is None:
        _instance = BulkProcessor()
    return _instance


# Backward compatibility
AsyncDocumentProcessor = BulkProcessor
get_async_processor = get_bulk_processor
