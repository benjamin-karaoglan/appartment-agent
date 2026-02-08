"""Documents API routes with comprehensive logging and multimodal support."""

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import PyPDF2
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.better_auth_security import get_current_user_hybrid as get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.i18n import get_local, get_output_language, translate
from app.models.document import Document, DocumentSummary
from app.models.user import User
from app.schemas.document import (
    BulkDeleteRequest,
    DiagnosticAnalysisResponse,
    DocumentRenameRequest,
    DocumentResponse,
    PVAGAnalysisResponse,
    TaxChargesAnalysisResponse,
)
from app.services.ai import get_document_analyzer
from app.services.ai.document_processor import get_document_processor
from app.services.documents import DocumentParser
from app.services.storage import get_storage_service

# Backward compatibility aliases
get_gemini_llm_service = get_document_analyzer
DocumentParsingService = DocumentParser

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazy initialization - don't initialize at module level for Cloud Run compatibility
_doc_parser = None


def get_doc_parser():
    """Get or create document parser (lazy initialization)."""
    global _doc_parser
    if _doc_parser is None:
        _doc_parser = DocumentParsingService()
    return _doc_parser


async def _regenerate_overall_synthesis(
    property_id: int, db: Session, output_language: str = "French"
):
    """
    Regenerate the overall property synthesis from all analyzed documents.

    Called after individual uploads and deletions to keep synthesis up-to-date.
    """
    try:
        # Fetch all analyzed documents for this property
        analyzed_docs = (
            db.query(Document)
            .filter(
                Document.property_id == property_id,
                Document.is_analyzed == True,
            )
            .all()
        )

        # Get existing synthesis record (category=NULL for overall)
        existing_synthesis = (
            db.query(DocumentSummary)
            .filter(DocumentSummary.property_id == property_id, DocumentSummary.category == None)
            .first()
        )

        # If no analyzed documents remain, delete synthesis
        if not analyzed_docs:
            if existing_synthesis:
                db.delete(existing_synthesis)
                db.commit()
                logger.info(f"Deleted synthesis for property {property_id} (no documents)")
            return

        # Build results list from stored analysis data
        results = []
        for doc in analyzed_docs:
            result_data: Dict[str, Any] = {
                "summary": doc.analysis_summary or "",
                "key_insights": doc.key_insights or [],
                "estimated_annual_cost": doc.estimated_annual_cost or 0.0,
                "one_time_costs": doc.one_time_costs or [],
            }
            # Include full extracted_data so the AI synthesizer has complete context
            # (e.g., detailed tax breakdown, diagnostic findings, charge details)
            if doc.extracted_data:
                try:
                    extracted = (
                        json.loads(doc.extracted_data)
                        if isinstance(doc.extracted_data, str)
                        else doc.extracted_data
                    )
                    result_data["extracted_data"] = extracted
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(
                {
                    "filename": doc.filename,
                    "document_type": doc.document_category,
                    "result": result_data,
                    "document_id": doc.id,
                }
            )

        # Call synthesize_results
        processor = get_document_processor()
        synthesis = await processor.synthesize_results(results, output_language=output_language)

        # Save/update DocumentSummary where category=NULL
        if not existing_synthesis:
            existing_synthesis = DocumentSummary(property_id=property_id)
            db.add(existing_synthesis)

        existing_synthesis.overall_summary = synthesis.get("summary", "")
        existing_synthesis.total_annual_cost = synthesis.get("total_annual_costs", 0.0)
        existing_synthesis.total_one_time_cost = synthesis.get("total_one_time_costs", 0.0)
        existing_synthesis.risk_level = synthesis.get("risk_level", "unknown")
        existing_synthesis.key_findings = synthesis.get("key_findings", [])
        existing_synthesis.recommendations = synthesis.get("recommendations", [])

        # Preserve user_overrides from previous synthesis_data when regenerating
        if existing_synthesis.synthesis_data:
            try:
                old_data = json.loads(existing_synthesis.synthesis_data)
                if "user_overrides" in old_data:
                    synthesis["user_overrides"] = old_data["user_overrides"]
            except (json.JSONDecodeError, TypeError):
                pass

        existing_synthesis.synthesis_data = json.dumps(synthesis)
        existing_synthesis.last_updated = datetime.utcnow()

        db.commit()
        logger.info(
            f"Regenerated synthesis for property {property_id} from {len(analyzed_docs)} documents"
        )

    except Exception as e:
        logger.error(
            f"Failed to regenerate synthesis for property {property_id}: {e}", exc_info=True
        )


def extract_text_from_pdf(
    file_path: str, storage_key: str = None, storage_bucket: str = None, locale: str = "fr"
) -> str:
    """
    Extract text from PDF file.

    Can read from local file path or from storage service if storage_key is provided.
    """
    from io import BytesIO

    text = ""
    try:
        if storage_key:
            # Read from storage service
            storage = get_storage_service()
            file_data = storage.download_file(storage_key, storage_bucket)
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_data))
        else:
            # Read from local file path (legacy support)
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)

        for page in pdf_reader.pages:
            text += page.extract_text()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("failed_extract_pdf", locale, error=str(e)),
        )
    return text


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    property_id: Optional[int] = Form(None),
    document_category: str = Form(...),
    document_subcategory: Optional[str] = Form(None),
    auto_parse: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Upload a document for analysis.

    Categories:
    - pv_ag: PV d'AG (assembly minutes)
    - diags: Diagnostics (subcategory: dpe, amiante, plomb, termite, electric, gas)
    - taxe_fonciere: Property tax documents
    - charges: Condominium charges documents
    """
    locale = get_local(request)

    logger.info(
        f"Document upload request - user: {current_user}, category: {document_category}, "
        f"subcategory: {document_subcategory}, property_id: {property_id}, filename: {file.filename}"
    )

    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file type attempted: {file_ext} for file {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("file_type_not_allowed", locale, ext=file_ext),
        )

    # Read file content
    try:
        content = await file.read()
        file_size = len(content)
        logger.info(f"File read successfully: {file.filename}, size: {file_size} bytes")
    except Exception as e:
        logger.error(f"Failed to read file {file.filename}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("failed_read_file", locale, error=str(e)),
        )

    # Calculate file hash for deduplication
    file_hash = hashlib.sha256(content).hexdigest()

    # Get user UUID for path structure
    user = db.query(User).filter(User.id == int(current_user)).first()
    if not user or not user.uuid:
        raise HTTPException(status_code=500, detail=translate("user_uuid_not_found", locale))
    user_uuid = user.uuid

    # Create document record first (to get UUID for storage path)
    try:
        # Generate UUID for document path
        doc_uuid = str(uuid.uuid4())

        document = Document(
            uuid=doc_uuid,
            user_id=int(current_user),
            property_id=property_id,
            filename=file.filename,
            file_path="",  # Will be updated after storage upload
            file_type=file_ext,
            document_category=document_category,
            document_subcategory=document_subcategory,
            file_size=file_size,
            file_hash=file_hash,
        )

        db.add(document)
        db.flush()  # Get the document ID
        document_id = document.id
        logger.info(f"Document record created with ID: {document_id}, UUID: {doc_uuid}")

        # Upload to storage service
        storage_service = get_storage_service()
        # Use UUIDs in path: {user_uuid}/documents/{doc_uuid}/{filename}
        storage_key = f"{user_uuid}/documents/{doc_uuid}/{file.filename}"

        storage_service.upload_file(
            file_data=content,
            filename=storage_key,
            content_type=file.content_type or "application/octet-stream",
            metadata={
                "document_uuid": doc_uuid,
                "user_uuid": user_uuid,
                "category": document_category,
                "subcategory": document_subcategory or "",
            },
        )
        logger.info(f"File uploaded to storage: {storage_key}")

        # Update document with storage info
        document.storage_key = storage_key
        document.storage_bucket = storage_service.bucket
        document.file_path = f"storage://{storage_service.bucket}/{storage_key}"

        db.commit()
        db.refresh(document)

    except Exception as e:
        logger.error(f"Failed to create document record: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("failed_create_document", locale, error=str(e)),
        )

    # Automatically parse document if requested
    if auto_parse and property_id:
        logger.info(f"Auto-parsing enabled for document ID {document.id}")
        output_language = get_output_language(locale)
        try:
            await get_doc_parser().parse_document(document, db, output_language=output_language)

            # Trigger aggregation if this is pv_ag or diags
            if document_category == "pv_ag":
                logger.info(f"Triggering PV AG aggregation for property {property_id}")
                await get_doc_parser().aggregate_pv_ag_summaries(
                    property_id, db, output_language=output_language
                )
            elif document_category == "diags":
                logger.info(f"Triggering diagnostic aggregation for property {property_id}")
                await get_doc_parser().aggregate_diagnostic_summaries(
                    property_id, db, output_language=output_language
                )

            # Regenerate overall synthesis after any upload
            logger.info(f"Triggering overall synthesis regeneration for property {property_id}")
            await _regenerate_overall_synthesis(property_id, db, output_language=output_language)
        except Exception as e:
            logger.error(f"Auto-parse failed for document ID {document.id}: {e}", exc_info=True)
            # Don't fail the upload if parsing fails - document is still saved
    elif not property_id:
        logger.info("Auto-parse skipped - no property_id provided")
    else:
        logger.info("Auto-parse disabled by request")

    db.refresh(document)
    logger.info(f"Document upload completed successfully: ID {document.id}")
    return document


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    request: Request,
    property_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """List all documents for the current user."""
    get_local(request)

    query = db.query(Document).filter(Document.user_id == int(current_user))

    if property_id:
        query = query.filter(Document.property_id == property_id)

    documents = query.all()
    return documents


@router.post("/bulk-delete")
async def bulk_delete_documents(
    request: Request,
    body: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Delete multiple documents at once."""
    locale = get_local(request)

    if not body.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("no_documents_to_delete", locale),
        )

    # Fetch all matching documents for this user
    documents = (
        db.query(Document)
        .filter(Document.id.in_(body.document_ids), Document.user_id == int(current_user))
        .all()
    )

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("document_not_found", locale)
        )

    # Collect unique property IDs for synthesis regeneration
    property_ids = set()
    storage_service = get_storage_service()

    for doc in documents:
        if doc.property_id:
            property_ids.add(doc.property_id)

        # Delete from storage
        if doc.storage_key:
            try:
                storage_service.delete_file(doc.storage_key, doc.storage_bucket)
            except Exception as e:
                logger.warning(f"Failed to delete file from storage: {e}")
        elif doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        db.delete(doc)

    db.commit()

    # Regenerate synthesis once per property
    output_language = get_output_language(get_local(request))
    for pid in property_ids:
        await _regenerate_overall_synthesis(pid, db, output_language=output_language)

    return {"deleted_count": len(documents)}


@router.patch("/{document_id}", response_model=DocumentResponse)
async def rename_document(
    request: Request,
    document_id: int,
    body: DocumentRenameRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Rename a document (display filename only, storage key unchanged)."""
    locale = get_local(request)

    new_filename = body.filename.strip()
    if not new_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("filename_cannot_be_empty", locale),
        )

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == int(current_user))
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("document_not_found", locale)
        )

    # Preserve original extension
    original_ext = os.path.splitext(document.filename)[1]
    new_ext = os.path.splitext(new_filename)[1]

    # If user provided the same extension, use as-is; otherwise append original extension
    if new_ext.lower() == original_ext.lower():
        document.filename = new_filename
    else:
        # Strip any extension from new name, then append original
        name_without_ext = os.path.splitext(new_filename)[0]
        document.filename = name_without_ext + original_ext

    db.commit()
    db.refresh(document)
    return document


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    request: Request,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Get a specific document."""
    locale = get_local(request)

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == int(current_user))
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("document_not_found", locale)
        )

    return document


@router.post("/{document_id}/analyze-pvag", response_model=PVAGAnalysisResponse)
async def analyze_pvag(
    request: Request,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Analyze PV d'AG document using Claude AI."""
    locale = get_local(request)

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == int(current_user))
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("document_not_found", locale)
        )

    # Extract text from document
    if document.file_type == ".pdf":
        document_text = extract_text_from_pdf(
            document.file_path,
            storage_key=document.storage_key,
            storage_bucket=document.storage_bucket,
            locale=locale,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=translate("only_pdf_pvag", locale)
        )

    # Analyze with Gemini
    gemini_service = get_gemini_llm_service()
    output_language = get_output_language(locale)
    analysis = await gemini_service.analyze_pvag_document(
        document_text, output_language=output_language
    )

    # Update document with analysis
    import json

    document.is_analyzed = True
    document.analysis_summary = analysis.get("summary", "")
    document.extracted_data = json.dumps(analysis)

    # Increment user's documents analyzed count
    user = db.query(User).filter(User.id == int(current_user)).first()
    if user:
        user.documents_analyzed_count = (user.documents_analyzed_count or 0) + 1

    db.commit()

    # Calculate total estimated costs
    estimated_costs = {
        "upcoming_works": sum(
            work.get("estimated_cost", 0) for work in analysis.get("upcoming_works", [])
        ),
        "total": sum(work.get("estimated_cost", 0) for work in analysis.get("upcoming_works", [])),
    }

    return PVAGAnalysisResponse(
        document_id=document_id,
        summary=analysis.get("summary", ""),
        upcoming_works=analysis.get("upcoming_works", []),
        estimated_costs=estimated_costs,
        risk_level=analysis.get("risk_level", "unknown"),
        key_findings=analysis.get("key_findings", []),
        recommendations=analysis.get("recommendations", []),
    )


@router.post("/{document_id}/analyze-diagnostic", response_model=DiagnosticAnalysisResponse)
async def analyze_diagnostic(
    request: Request,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Analyze diagnostic document (DPE, amiante, plomb) using Claude AI."""
    locale = get_local(request)

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == int(current_user))
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("document_not_found", locale)
        )

    # Extract text
    if document.file_type == ".pdf":
        document_text = extract_text_from_pdf(
            document.file_path,
            storage_key=document.storage_key,
            storage_bucket=document.storage_bucket,
            locale=locale,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=translate("only_pdf_supported", locale)
        )

    # Analyze with Gemini
    gemini_service = get_gemini_llm_service()
    output_language = get_output_language(locale)
    analysis = await gemini_service.analyze_diagnostic_document(
        document_text, output_language=output_language
    )

    # Update document
    import json

    document.is_analyzed = True
    document.analysis_summary = analysis.get("summary", "")
    document.extracted_data = json.dumps(analysis)
    document.risk_flags = json.dumps(analysis.get("risk_flags", []))

    # Increment user's documents analyzed count
    user = db.query(User).filter(User.id == int(current_user)).first()
    if user:
        user.documents_analyzed_count = (user.documents_analyzed_count or 0) + 1

    db.commit()

    return DiagnosticAnalysisResponse(document_id=document_id, **analysis)


@router.post("/{document_id}/analyze-tax-charges", response_model=TaxChargesAnalysisResponse)
async def analyze_tax_charges(
    request: Request,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Analyze tax or charges document using Claude AI."""
    locale = get_local(request)

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == int(current_user))
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("document_not_found", locale)
        )

    # Extract text
    if document.file_type == ".pdf":
        document_text = extract_text_from_pdf(
            document.file_path,
            storage_key=document.storage_key,
            storage_bucket=document.storage_bucket,
            locale=locale,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=translate("only_pdf_supported", locale)
        )

    # Determine document type from category
    doc_type = "taxe_fonciere" if "tax" in document.document_category.lower() else "charges"

    # Analyze with Gemini
    gemini_service = get_gemini_llm_service()
    output_language = get_output_language(locale)
    analysis = await gemini_service.analyze_tax_charges_document(
        document_text, doc_type, output_language=output_language
    )

    # Update document
    import json

    document.is_analyzed = True
    document.analysis_summary = analysis.get("summary", "")
    document.extracted_data = json.dumps(analysis)

    # Increment user's documents analyzed count
    user = db.query(User).filter(User.id == int(current_user)).first()
    if user:
        user.documents_analyzed_count = (user.documents_analyzed_count or 0) + 1

    db.commit()

    return TaxChargesAnalysisResponse(document_id=document_id, **analysis)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    request: Request,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Delete a document."""
    locale = get_local(request)

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == int(current_user))
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("document_not_found", locale)
        )

    # Capture property_id before deletion for re-synthesis
    property_id = document.property_id

    # Delete file from storage service
    if document.storage_key:
        try:
            storage_service = get_storage_service()
            storage_service.delete_file(document.storage_key, document.storage_bucket)
            logger.info(f"Deleted file from storage: {document.storage_key}")
        except Exception as e:
            logger.warning(f"Failed to delete file from storage: {e}")
    # Legacy: Delete from local disk if exists
    elif document.file_path and os.path.exists(document.file_path):
        os.remove(document.file_path)

    db.delete(document)
    db.commit()

    # Regenerate overall synthesis after deletion
    if property_id:
        locale = get_local(request)
        output_language = get_output_language(locale)
        await _regenerate_overall_synthesis(property_id, db, output_language=output_language)

    return None


@router.get("/summaries/{property_id}")
async def get_document_summaries(
    request: Request,
    property_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Get aggregated document summaries for a property.

    Returns comprehensive analysis of all documents by category:
    - pv_ag: All assembly minutes synthesized
    - diags: All diagnostics summarized
    - taxe_fonciere: Tax information
    - charges: Charges information
    """
    locale = get_local(request)

    from app.models.property import Property

    # Verify property belongs to user
    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    query = db.query(DocumentSummary).filter(DocumentSummary.property_id == property_id)

    if category:
        query = query.filter(DocumentSummary.category == category)

    summaries = query.all()

    # Add document count to response
    result = []
    for summary in summaries:
        summary_dict = {
            "id": summary.id,
            "property_id": summary.property_id,
            "category": summary.category,
            "summary": summary.summary,
            "key_findings": summary.key_findings,
            "total_estimated_annual_cost": summary.total_estimated_annual_cost,
            "total_one_time_costs": summary.total_one_time_costs,
            "cost_breakdown": summary.cost_breakdown,
            "copropriete_insights": summary.copropriete_insights,
            "diagnostic_issues": summary.diagnostic_issues,
            "created_at": summary.created_at,
            "updated_at": summary.updated_at,
            "document_count": db.query(Document)
            .filter(
                Document.property_id == property_id,
                Document.document_category == summary.category,
                Document.is_analyzed == True,
            )
            .count(),
        }
        result.append(summary_dict)

    return result


@router.get("/synthesis/{property_id}")
async def get_property_synthesis(
    request: Request,
    property_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Get the overall AI synthesis for a property (from bulk upload).

    Returns the comprehensive analysis that covers all uploaded documents.
    """
    locale = get_local(request)

    from app.models.property import Property

    # Verify property belongs to user
    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    # Get synthesis (category is NULL for overall synthesis)
    synthesis = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.property_id == property_id, DocumentSummary.category == None)
        .first()
    )

    if not synthesis:
        return None

    synthesis_data = None
    if synthesis.synthesis_data:
        try:
            synthesis_data = json.loads(synthesis.synthesis_data)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse synthesis_data for property {property_id}")

    return {
        "id": synthesis.id,
        "property_id": synthesis.property_id,
        "overall_summary": synthesis.overall_summary,
        "risk_level": synthesis.risk_level,
        "total_annual_cost": synthesis.total_annual_cost,
        "total_one_time_cost": synthesis.total_one_time_cost,
        "key_findings": synthesis.key_findings,
        "recommendations": synthesis.recommendations,
        "last_updated": synthesis.last_updated,
        "synthesis_data": synthesis_data,
    }


@router.patch("/synthesis/{property_id}/overrides")
async def update_synthesis_overrides(
    request: Request,
    property_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Save user overrides (tantièmes, etc.) into the synthesis_data JSON.

    Preserves all existing synthesis data and merges user_overrides into it.
    """
    locale = get_local(request)

    from app.models.property import Property

    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    body = await request.json()

    synthesis = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.property_id == property_id, DocumentSummary.category == None)
        .first()
    )

    if not synthesis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No synthesis found for this property"
        )

    # Parse existing synthesis_data
    synthesis_data = {}
    if synthesis.synthesis_data:
        try:
            synthesis_data = json.loads(synthesis.synthesis_data)
        except (json.JSONDecodeError, TypeError):
            synthesis_data = {}

    # Merge user_overrides
    user_overrides = synthesis_data.get("user_overrides", {})
    if "lot_tantiemes" in body:
        user_overrides["lot_tantiemes"] = body["lot_tantiemes"]
    if "total_tantiemes" in body:
        user_overrides["total_tantiemes"] = body["total_tantiemes"]

    synthesis_data["user_overrides"] = user_overrides
    synthesis.synthesis_data = json.dumps(synthesis_data)
    synthesis.last_updated = datetime.utcnow()
    db.commit()

    return {"status": "ok", "user_overrides": user_overrides}


@router.post("/summaries/{property_id}/regenerate")
async def regenerate_summaries(
    request: Request,
    property_id: int,
    category: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Manually trigger regeneration of document summaries for a property category.

    Useful after uploading multiple documents.
    """
    locale = get_local(request)

    from app.models.property import Property

    # Verify property belongs to user
    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    output_language = get_output_language(locale)
    try:
        if category == "pv_ag":
            summary = await get_doc_parser().aggregate_pv_ag_summaries(
                property_id, db, output_language=output_language
            )
        elif category == "diags":
            summary = await get_doc_parser().aggregate_diagnostic_summaries(
                property_id, db, output_language=output_language
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=translate("aggregation_not_supported", locale, category=category),
            )

        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=translate("no_documents_to_aggregate", locale),
            )

        return {
            "id": summary.id,
            "property_id": summary.property_id,
            "category": summary.category,
            "summary": summary.summary,
            "key_findings": summary.key_findings,
            "total_estimated_annual_cost": summary.total_estimated_annual_cost,
            "total_one_time_costs": summary.total_one_time_costs,
            "cost_breakdown": summary.cost_breakdown,
            "copropriete_insights": summary.copropriete_insights,
            "diagnostic_issues": summary.diagnostic_issues,
            "created_at": summary.created_at,
            "updated_at": summary.updated_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("failed_regenerate_summary", locale, error=str(e)),
        )


@router.post("/synthesis/{property_id}/regenerate-overall")
async def regenerate_overall_synthesis(
    request: Request,
    property_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Manually trigger regeneration of the overall property synthesis.

    Rebuilds synthesis from all analyzed documents for the property.
    """
    locale = get_local(request)

    from app.models.property import Property

    # Verify property belongs to user
    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    output_language = get_output_language(locale)
    await _regenerate_overall_synthesis(property_id, db, output_language=output_language)

    # Return the updated synthesis
    synthesis = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.property_id == property_id, DocumentSummary.category == None)
        .first()
    )

    if not synthesis:
        return None

    regen_synthesis_data = None
    if synthesis.synthesis_data:
        try:
            regen_synthesis_data = json.loads(synthesis.synthesis_data)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse synthesis_data for property {property_id}")

    return {
        "id": synthesis.id,
        "property_id": synthesis.property_id,
        "overall_summary": synthesis.overall_summary,
        "risk_level": synthesis.risk_level,
        "total_annual_cost": synthesis.total_annual_cost,
        "total_one_time_cost": synthesis.total_one_time_cost,
        "key_findings": synthesis.key_findings,
        "recommendations": synthesis.recommendations,
        "last_updated": synthesis.last_updated,
        "synthesis_data": regen_synthesis_data,
    }


@router.post("/upload-async", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_async(
    request: Request,
    file: UploadFile = File(...),
    property_id: Optional[int] = Form(None),
    document_category: str = Form(...),
    document_subcategory: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Upload a document for async processing with MinIO.

    This endpoint:
    1. Saves file to MinIO object storage
    2. Creates document record with pending status
    3. Returns immediately without waiting for analysis

    Categories:
    - pv_ag: PV d'AG (assembly minutes)
    - diags: Diagnostics (subcategory: dpe, amiante, plomb, termite, electric, gas)
    - taxe_fonciere: Property tax documents
    - charges: Condominium charges documents
    """
    locale = get_local(request)

    logger.info(
        f"Async document upload - user: {current_user}, category: {document_category}, "
        f"subcategory: {document_subcategory}, property_id: {property_id}, filename: {file.filename}"
    )

    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file type: {file_ext} for file {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("file_type_not_allowed", locale, ext=file_ext),
        )

    # Read file content
    try:
        content = await file.read()
        file_size = len(content)
        logger.info(f"File read successfully: {file.filename}, size: {file_size} bytes")
    except Exception as e:
        logger.error(f"Failed to read file {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("failed_read_file", locale, error=str(e)),
        )

    # Calculate file hash
    file_hash = hashlib.sha256(content).hexdigest()

    # Get user UUID for path structure
    user = db.query(User).filter(User.id == int(current_user)).first()
    if not user or not user.uuid:
        raise HTTPException(status_code=500, detail=translate("user_uuid_not_found", locale))
    user_uuid = user.uuid

    # Create document record first (to get UUID)
    try:
        # Generate UUID for document path
        doc_uuid = str(uuid.uuid4())

        document = Document(
            uuid=doc_uuid,
            user_id=int(current_user),
            property_id=property_id,
            filename=file.filename,
            file_path="",  # Will be updated after storage upload
            file_type=file_ext,
            document_category=document_category,
            document_subcategory=document_subcategory,
            file_size=file_size,
            file_hash=file_hash,
            processing_status="pending",
        )
        db.add(document)
        db.flush()  # Get the document ID
        document_id = document.id

        logger.info(f"Document record created with ID: {document_id}, UUID: {doc_uuid}")

        # Upload to storage
        storage_service = get_storage_service()
        # Use UUIDs in path: {user_uuid}/documents/{doc_uuid}/{filename}
        storage_key = f"{user_uuid}/documents/{doc_uuid}/{file.filename}"

        storage_service.upload_file(
            file_data=content,
            filename=storage_key,
            content_type=file.content_type or "application/octet-stream",
            metadata={
                "document_uuid": doc_uuid,
                "user_uuid": user_uuid,
                "category": document_category,
                "subcategory": document_subcategory or "",
            },
        )

        logger.info(f"File uploaded to storage: {storage_key}")

        # Update document with storage info
        document.storage_key = storage_key
        document.storage_bucket = storage_service.bucket
        document.file_path = f"storage://{storage_service.bucket}/{storage_key}"

        # Document will be processed via async_processor for bulk uploads
        # or synchronously via doc_parser for single uploads
        logger.info(f"Document {document_id} uploaded, ready for processing")

        db.commit()
        db.refresh(document)

        logger.info(f"Async upload complete for document {document_id}")

        return DocumentResponse(
            id=document.id,
            filename=document.filename,
            file_type=document.file_type,
            document_category=document.document_category,
            document_subcategory=document.document_subcategory,
            is_analyzed=document.is_analyzed,
            upload_date=document.upload_date,
            file_size=document.file_size,
            property_id=document.property_id,
            processing_status=document.processing_status,
            workflow_id=document.workflow_id,
        )

    except Exception as e:
        logger.error(f"Failed to upload document: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("failed_upload_document", locale, error=str(e)),
        )


@router.get("/{document_id}/status")
async def get_document_status(
    request: Request,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Get the processing status of a document.

    Returns:
    - processing_status: pending, processing, completed, failed
    - workflow_id: Temporal workflow ID (if using async processing)
    - is_analyzed: Whether analysis is complete
    - processing_error: Error message if failed
    """
    locale = get_local(request)

    logger.info(f"Status check for document {document_id}")

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == int(current_user))
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("document_not_found", locale)
        )

    return {
        "document_id": document.id,
        "filename": document.filename,
        "processing_status": document.processing_status,
        "is_analyzed": document.is_analyzed,
        "workflow_id": document.workflow_id,
        "workflow_run_id": document.workflow_run_id,
        "processing_started_at": document.processing_started_at,
        "processing_completed_at": document.processing_completed_at,
        "processing_error": document.processing_error,
    }


@router.post("/bulk-upload", status_code=status.HTTP_202_ACCEPTED)
async def bulk_upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    property_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Upload multiple documents at once with intelligent classification and processing.

    This endpoint uses Gemini AI to:
    1. Automatically classify document types (PV AG, diagnostics, taxes, charges)
    2. Process each document with specialized prompts
    3. Synthesize results across all documents
    4. Generate comprehensive property summary

    Returns:
    - workflow_id: ID to track the bulk processing workflow
    - document_ids: List of created document IDs
    - status: "processing"
    """
    locale = get_local(request)

    logger.info(
        f"Bulk upload initiated - user: {current_user}, property_id: {property_id}, "
        f"{len(files)} files"
    )

    if not files or len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=translate("no_files_provided", locale)
        )

    if len(files) > 50:  # Reasonable limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=translate("max_files_exceeded", locale)
        )

    # Verify property belongs to user
    from app.models.property import Property

    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    # Get user UUID for path structure
    user = db.query(User).filter(User.id == int(current_user)).first()
    if not user or not user.uuid:
        raise HTTPException(status_code=500, detail=translate("user_uuid_not_found", locale))
    user_uuid = user.uuid

    uploaded_documents = []
    document_uploads_info = []

    try:
        # Step 1: Upload all files to storage and create document records
        storage_service = get_storage_service()

        for file in files:
            # Validate file
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in settings.ALLOWED_EXTENSIONS:
                logger.warning(f"Skipping invalid file type: {file.filename}")
                continue

            # Read file
            content = await file.read()
            file_size = len(content)
            file_hash = hashlib.sha256(content).hexdigest()

            # Generate UUID for document path
            doc_uuid = str(uuid.uuid4())

            # Create document record
            document = Document(
                uuid=doc_uuid,
                user_id=int(current_user),
                property_id=property_id,
                filename=file.filename,
                file_path="",  # Will be updated
                file_type=file_ext,
                document_category="pending_classification",  # Agent will classify
                file_size=file_size,
                file_hash=file_hash,
                processing_status="pending",
            )
            db.add(document)
            db.flush()  # Get document ID

            # Upload to storage with UUIDs in path: {user_uuid}/documents/{doc_uuid}/{filename}
            storage_key = f"{user_uuid}/documents/{doc_uuid}/{file.filename}"
            storage_service.upload_file(
                file_data=content,
                filename=storage_key,
                content_type=file.content_type or "application/octet-stream",
                metadata={
                    "document_uuid": doc_uuid,
                    "user_uuid": user_uuid,
                    "property_id": str(property_id),
                },
            )

            # Update document
            document.storage_key = storage_key
            document.storage_bucket = storage_service.bucket
            document.file_path = f"storage://{storage_service.bucket}/{storage_key}"

            uploaded_documents.append(document)
            document_uploads_info.append(
                {
                    "document_id": document.id,
                    "document_uuid": doc_uuid,
                    "storage_key": storage_key,
                    "filename": file.filename,
                }
            )

            logger.info(f"Uploaded {file.filename} to storage: {storage_key}")

        db.commit()

        # Step 2: Start async background processing
        if len(uploaded_documents) > 0:
            try:
                from app.services.documents import get_bulk_processor

                # Generate workflow ID
                workflow_id = (
                    f"bulk-{property_id}-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:8]}"
                )

                # Update documents with workflow ID
                for doc in uploaded_documents:
                    doc.workflow_id = workflow_id
                    doc.processing_status = "processing"

                db.commit()

                # Start background processing
                output_language = get_output_language(locale)
                processor = get_bulk_processor()
                processor.start_background_task(
                    workflow_id=workflow_id,
                    property_id=property_id,
                    document_uploads=document_uploads_info,
                    output_language=output_language,
                )

                logger.info(f"Started async bulk processing: {workflow_id}")

                return {
                    "status": "processing",
                    "workflow_id": workflow_id,
                    "document_ids": [doc.id for doc in uploaded_documents],
                    "total_files": len(uploaded_documents),
                    "message": (
                        f"Successfully uploaded {len(uploaded_documents)} documents. "
                        "The AI agent is now classifying and processing them. "
                        "Check the status to see progress."
                    ),
                }

            except Exception as e:
                logger.error(f"Failed to start processing: {e}", exc_info=True)
                # Mark documents as failed
                for doc in uploaded_documents:
                    doc.processing_status = "failed"
                    doc.processing_error = f"Failed to start processing: {str(e)}"
                db.commit()

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=translate("failed_start_processing", locale, error=str(e)),
                )
        else:
            return {
                "status": "pending",
                "document_ids": [],
                "total_files": 0,
                "message": "No valid documents to process",
            }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("bulk_upload_failed", locale, error=str(e)),
        )


@router.get("/bulk-status/{workflow_id}")
async def get_bulk_processing_status(
    request: Request,
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Get the status of a bulk document processing workflow.

    Returns:
    - status: Overall workflow status
    - documents: List of document statuses
    - synthesis: Final synthesis (if complete)
    - progress: Processing progress
    """
    locale = get_local(request)

    logger.info(f"Bulk status check for workflow {workflow_id}")

    # Get all documents for this workflow
    documents = (
        db.query(Document)
        .filter(Document.workflow_id == workflow_id, Document.user_id == int(current_user))
        .all()
    )

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("workflow_not_found", locale)
        )

    property_id = documents[0].property_id

    # Get synthesis if available (category=NULL for overall synthesis)
    synthesis = (
        db.query(DocumentSummary)
        .filter(DocumentSummary.property_id == property_id, DocumentSummary.category == None)
        .first()
    )

    logger.info(f"Synthesis found for property {property_id}: {synthesis is not None}")
    if synthesis:
        logger.info(
            f"Synthesis data - risk: {synthesis.risk_level}, summary length: {len(synthesis.overall_summary) if synthesis.overall_summary else 0}"
        )

    # Calculate progress
    total = len(documents)
    completed = sum(1 for d in documents if d.processing_status == "completed")
    failed = sum(1 for d in documents if d.processing_status == "failed")
    processing = sum(1 for d in documents if d.processing_status == "processing")
    pending = sum(1 for d in documents if d.processing_status == "pending")

    # Determine overall status
    if completed == total:
        overall_status = "completed"
    elif failed == total:
        overall_status = "failed"
    elif processing > 0 or pending > 0:
        overall_status = "processing"
    else:
        overall_status = "unknown"

    response_data = {
        "workflow_id": workflow_id,
        "property_id": property_id,
        "status": overall_status,
        "progress": {
            "total": total,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "percentage": int((completed / total) * 100) if total > 0 else 0,
        },
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "document_category": doc.document_category,
                "document_subcategory": doc.document_subcategory,
                "processing_status": doc.processing_status,
                "is_analyzed": doc.is_analyzed,
                "processing_error": doc.processing_error,
            }
            for doc in documents
        ],
        "synthesis": {
            "summary": synthesis.overall_summary if synthesis else None,
            "total_annual_cost": synthesis.total_annual_cost if synthesis else None,
            "total_one_time_cost": synthesis.total_one_time_cost if synthesis else None,
            "risk_level": synthesis.risk_level if synthesis else None,
            "key_findings": synthesis.key_findings if synthesis else [],
            "recommendations": synthesis.recommendations if synthesis else [],
            "synthesis_data": json.loads(synthesis.synthesis_data)
            if synthesis and synthesis.synthesis_data
            else None,
        }
        if synthesis
        else None,
    }

    logger.info(f"Returning synthesis: {response_data['synthesis'] is not None}")

    return response_data
