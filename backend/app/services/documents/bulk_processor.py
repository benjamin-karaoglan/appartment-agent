"""
Bulk Processor - Async document processing orchestrator.

Handles bulk document uploads with parallel processing and synthesis.
"""

import asyncio
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


def prepare_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """Prepare a PDF for processing: extract text and metadata using PyMuPDF."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)

        # Extract text from all pages
        text_parts = []
        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                text_parts.append(text)

        doc.close()

        extracted_text = "\n\n".join(text_parts)
        text_extractable = len(extracted_text) > 500

        logger.info(
            f"PDF prepared: {page_count} pages, "
            f"{len(extracted_text)} chars extracted, "
            f"text_extractable={text_extractable}"
        )

        return {
            "pdf_data": pdf_bytes,
            "text_extractable": text_extractable,
            "extracted_text": extracted_text if text_extractable else "",
            "page_count": page_count,
        }

    except Exception as e:
        logger.error(f"PDF preparation error: {e}")
        return {
            "pdf_data": pdf_bytes,
            "text_extractable": False,
            "extracted_text": "",
            "page_count": 0,
        }


class BulkProcessor:
    """
    Orchestrates async bulk document processing.

    Flow:
    1. Download files from storage
    2. Prepare PDFs (extract text + metadata)
    3. Process each document with AI (native PDF)
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

            # Step 2: Prepare PDFs (text extraction + metadata)
            logger.info("Preparing PDF documents...")
            prepared_docs = await self._prepare_documents(file_data_list)

            # Step 3: Process all documents in parallel
            logger.info(f"Processing {len(document_uploads)} documents in parallel...")
            processor = get_document_processor()

            async def process_and_save(i: int, upload: Dict[str, Any]) -> Dict[str, Any]:
                """Process a single document and save the result."""
                logger.info(f"Starting {i+1}/{len(document_uploads)}: {upload['filename']}")
                doc_data = {
                    "filename": upload["filename"],
                    "pdf_data": prepared_docs[i]["pdf_data"],
                    "text_extractable": prepared_docs[i]["text_extractable"],
                    "extracted_text": prepared_docs[i]["extracted_text"],
                    "page_count": prepared_docs[i]["page_count"],
                    "document_id": upload["document_id"],
                }
                result = await processor.process_document(
                    doc_data,
                    output_language=output_language,
                )
                await self._save_document_result(db, result)
                logger.info(f"Completed {i+1}/{len(document_uploads)}: {upload['filename']}")
                return result

            tasks = [process_and_save(i, upload) for i, upload in enumerate(document_uploads)]
            results = await asyncio.gather(*tasks)

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

        async def download_one(storage_key: str) -> bytes:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, storage.download_file, storage_key)

        tasks = [download_one(upload["storage_key"]) for upload in document_uploads]
        return await asyncio.gather(*tasks)

    async def _prepare_documents(self, file_data_list: List[bytes]) -> List[Dict[str, Any]]:
        """Prepare PDFs in parallel: extract text and metadata."""

        async def prepare_one(file_data: bytes) -> Dict[str, Any]:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, prepare_pdf, file_data)

        tasks = [prepare_one(data) for data in file_data_list]
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

        # Preserve user_overrides from previous synthesis_data when regenerating
        if summary.synthesis_data:
            try:
                old_data = json.loads(summary.synthesis_data)
                if "user_overrides" in old_data:
                    synthesis["user_overrides"] = old_data["user_overrides"]
            except (json.JSONDecodeError, TypeError):
                pass

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
