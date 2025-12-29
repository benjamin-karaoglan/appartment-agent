"""Documents API routes with comprehensive logging and multimodal support."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import os
import uuid
import hashlib
import PyPDF2

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.document import Document
from app.schemas.document import (
    DocumentResponse,
    PVAGAnalysisResponse,
    DiagnosticAnalysisResponse,
    TaxChargesAnalysisResponse
)
from app.services.claude_service import claude_service
from app.services.document_service_v2 import DocumentParsingService  # Use new multimodal service
from app.models.document import DocumentSummary
from app.schemas.document import DocumentSummaryResponse
from app.services.minio_service import get_minio_service
from app.workflows.client import get_temporal_client

logger = logging.getLogger(__name__)
router = APIRouter()
doc_parser = DocumentParsingService()


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file."""
    text = ""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract text from PDF: {str(e)}"
        )
    return text


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    property_id: Optional[int] = Form(None),
    document_category: str = Form(...),
    document_subcategory: Optional[str] = Form(None),
    auto_parse: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Upload a document for analysis.

    Categories:
    - pv_ag: PV d'AG (assembly minutes)
    - diags: Diagnostics (subcategory: dpe, amiante, plomb, termite, electric, gas)
    - taxe_fonciere: Property tax documents
    - charges: Condominium charges documents
    """
    logger.info(f"Document upload request - user: {current_user}, category: {document_category}, "
                f"subcategory: {document_subcategory}, property_id: {property_id}, filename: {file.filename}")

    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file type attempted: {file_ext} for file {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed"
        )

    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    logger.debug(f"Saving file to: {file_path}")

    # Save file
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        file_size = len(content)
        logger.info(f"File saved successfully: {unique_filename}, size: {file_size} bytes")
    except Exception as e:
        logger.error(f"Failed to save file {file.filename}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    # Create document record
    try:
        document = Document(
            user_id=int(current_user),
            property_id=property_id,
            filename=file.filename,
            file_path=file_path,
            file_type=file_ext,
            document_category=document_category,
            document_subcategory=document_subcategory,
            file_size=file_size
        )

        db.add(document)
        db.commit()
        db.refresh(document)
        logger.info(f"Document record created with ID: {document.id}")
    except Exception as e:
        logger.error(f"Failed to create document record: {e}", exc_info=True)
        # Clean up file if database insert fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document record: {str(e)}"
        )

    # Automatically parse document if requested
    if auto_parse and property_id:
        logger.info(f"Auto-parsing enabled for document ID {document.id}")
        try:
            await doc_parser.parse_document(document, db)

            # Trigger aggregation if this is pv_ag or diags
            if document_category == "pv_ag":
                logger.info(f"Triggering PV AG aggregation for property {property_id}")
                await doc_parser.aggregate_pv_ag_summaries(property_id, db)
            elif document_category == "diags":
                logger.info(f"Triggering diagnostic aggregation for property {property_id}")
                await doc_parser.aggregate_diagnostic_summaries(property_id, db)
        except Exception as e:
            logger.error(f"Auto-parse failed for document ID {document.id}: {e}", exc_info=True)
            # Don't fail the upload if parsing fails - document is still saved
    elif not property_id:
        logger.info(f"Auto-parse skipped - no property_id provided")
    else:
        logger.info(f"Auto-parse disabled by request")

    db.refresh(document)
    logger.info(f"Document upload completed successfully: ID {document.id}")
    return document


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    property_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """List all documents for the current user."""
    query = db.query(Document).filter(Document.user_id == int(current_user))

    if property_id:
        query = query.filter(Document.property_id == property_id)

    documents = query.all()
    return documents


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get a specific document."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == int(current_user)
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return document


@router.post("/{document_id}/analyze-pvag", response_model=PVAGAnalysisResponse)
async def analyze_pvag(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Analyze PV d'AG document using Claude AI."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == int(current_user)
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Extract text from document
    if document.file_type == ".pdf":
        document_text = extract_text_from_pdf(document.file_path)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported for PV d'AG analysis"
        )

    # Analyze with Claude
    analysis = await claude_service.analyze_pvag_document(document_text)

    # Update document with analysis
    import json
    document.is_analyzed = True
    document.analysis_summary = analysis.get("summary", "")
    document.extracted_data = json.dumps(analysis)

    db.commit()

    # Calculate total estimated costs
    estimated_costs = {
        "upcoming_works": sum(
            work.get("estimated_cost", 0) for work in analysis.get("upcoming_works", [])
        ),
        "total": sum(
            work.get("estimated_cost", 0) for work in analysis.get("upcoming_works", [])
        )
    }

    return PVAGAnalysisResponse(
        document_id=document_id,
        summary=analysis.get("summary", ""),
        upcoming_works=analysis.get("upcoming_works", []),
        estimated_costs=estimated_costs,
        risk_level=analysis.get("risk_level", "unknown"),
        key_findings=analysis.get("key_findings", []),
        recommendations=analysis.get("recommendations", [])
    )


@router.post("/{document_id}/analyze-diagnostic", response_model=DiagnosticAnalysisResponse)
async def analyze_diagnostic(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Analyze diagnostic document (DPE, amiante, plomb) using Claude AI."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == int(current_user)
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Extract text
    if document.file_type == ".pdf":
        document_text = extract_text_from_pdf(document.file_path)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )

    # Analyze with Claude
    analysis = await claude_service.analyze_diagnostic_document(document_text)

    # Update document
    import json
    document.is_analyzed = True
    document.analysis_summary = analysis.get("summary", "")
    document.extracted_data = json.dumps(analysis)
    document.risk_flags = json.dumps(analysis.get("risk_flags", []))

    db.commit()

    return DiagnosticAnalysisResponse(
        document_id=document_id,
        **analysis
    )


@router.post("/{document_id}/analyze-tax-charges", response_model=TaxChargesAnalysisResponse)
async def analyze_tax_charges(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Analyze tax or charges document using Claude AI."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == int(current_user)
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Extract text
    if document.file_type == ".pdf":
        document_text = extract_text_from_pdf(document.file_path)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )

    # Determine document type from category
    doc_type = "taxe_fonciere" if "tax" in document.document_category.lower() else "charges"

    # Analyze with Claude
    analysis = await claude_service.analyze_tax_charges_document(document_text, doc_type)

    # Update document
    import json
    document.is_analyzed = True
    document.analysis_summary = analysis.get("summary", "")
    document.extracted_data = json.dumps(analysis)

    db.commit()

    return TaxChargesAnalysisResponse(
        document_id=document_id,
        **analysis
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Delete a document."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == int(current_user)
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Delete file from disk
    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    db.delete(document)
    db.commit()
    return None


@router.get("/summaries/{property_id}")
async def get_document_summaries(
    property_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get aggregated document summaries for a property.

    Returns comprehensive analysis of all documents by category:
    - pv_ag: All assembly minutes synthesized
    - diags: All diagnostics summarized
    - taxe_fonciere: Tax information
    - charges: Charges information
    """
    from app.models.property import Property

    # Verify property belongs to user
    property = db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == int(current_user)
    ).first()

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    query = db.query(DocumentSummary).filter(
        DocumentSummary.property_id == property_id
    )

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
            "document_count": db.query(Document).filter(
                Document.property_id == property_id,
                Document.document_category == summary.category,
                Document.is_analyzed == True
            ).count()
        }
        result.append(summary_dict)

    return result


@router.post("/summaries/{property_id}/regenerate")
async def regenerate_summaries(
    property_id: int,
    category: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Manually trigger regeneration of document summaries for a property category.

    Useful after uploading multiple documents.
    """
    from app.models.property import Property

    # Verify property belongs to user
    property = db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == int(current_user)
    ).first()

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    try:
        if category == "pv_ag":
            summary = await doc_parser.aggregate_pv_ag_summaries(property_id, db)
        elif category == "diags":
            summary = await doc_parser.aggregate_diagnostic_summaries(property_id, db)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Aggregation not supported for category: {category}"
            )

        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No documents found to aggregate"
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
            "updated_at": summary.updated_at
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate summary: {str(e)}"
        )


@router.post("/upload-async", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_async(
    file: UploadFile = File(...),
    property_id: Optional[int] = Form(None),
    document_category: str = Form(...),
    document_subcategory: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Upload a document for async processing with MinIO and Temporal.

    This endpoint:
    1. Saves file to MinIO object storage
    2. Creates document record with pending status
    3. Optionally starts Temporal workflow for async processing (if ENABLE_TEMPORAL_WORKFLOWS=true)
    4. Returns immediately without waiting for analysis

    Categories:
    - pv_ag: PV d'AG (assembly minutes)
    - diags: Diagnostics (subcategory: dpe, amiante, plomb, termite, electric, gas)
    - taxe_fonciere: Property tax documents
    - charges: Condominium charges documents
    """
    logger.info(f"Async document upload - user: {current_user}, category: {document_category}, "
                f"subcategory: {document_subcategory}, property_id: {property_id}, filename: {file.filename}")

    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file type: {file_ext} for file {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed"
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
            detail=f"Failed to read file: {str(e)}"
        )

    # Calculate file hash
    file_hash = hashlib.sha256(content).hexdigest()

    # Create document record first (to get ID)
    try:
        document = Document(
            user_id=int(current_user),
            property_id=property_id,
            filename=file.filename,
            file_path="",  # Will be updated after MinIO upload
            file_type=file_ext,
            document_category=document_category,
            document_subcategory=document_subcategory,
            file_size=file_size,
            file_hash=file_hash,
            processing_status="pending"
        )
        db.add(document)
        db.flush()  # Get the document ID
        document_id = document.id

        logger.info(f"Document record created with ID: {document_id}")

        # Upload to MinIO
        minio_service = get_minio_service()
        minio_key = f"documents/{document_id}/{file.filename}"

        minio_service.upload_file(
            file_data=content,
            object_name=minio_key,
            content_type=file.content_type or "application/octet-stream",
            metadata={
                "document_id": str(document_id),
                "user_id": str(current_user),
                "category": document_category,
                "subcategory": document_subcategory or ""
            }
        )

        logger.info(f"File uploaded to MinIO: {minio_key}")

        # Update document with MinIO info
        document.minio_key = minio_key
        document.minio_bucket = settings.MINIO_BUCKET
        document.file_path = f"minio://{settings.MINIO_BUCKET}/{minio_key}"

        # Start Temporal workflow if enabled
        if settings.ENABLE_TEMPORAL_WORKFLOWS:
            try:
                temporal_client = get_temporal_client()
                document_type = document_subcategory or document_category

                workflow_info = await temporal_client.start_document_processing(
                    document_id=document_id,
                    minio_key=minio_key,
                    document_type=document_type
                )

                document.workflow_id = workflow_info["workflow_id"]
                document.workflow_run_id = workflow_info["workflow_run_id"]

                logger.info(f"Started Temporal workflow: {workflow_info['workflow_id']}")

            except Exception as e:
                logger.error(f"Failed to start Temporal workflow: {e}")
                # Don't fail the upload, just log the error
                document.processing_error = f"Failed to start workflow: {str(e)}"
        else:
            logger.info("Temporal workflows disabled, document will be processed synchronously later")

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
            workflow_id=document.workflow_id
        )

    except Exception as e:
        logger.error(f"Failed to upload document: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get the processing status of a document.

    Returns:
    - processing_status: pending, processing, completed, failed
    - workflow_id: Temporal workflow ID (if using async processing)
    - is_analyzed: Whether analysis is complete
    - processing_error: Error message if failed
    """
    logger.info(f"Status check for document {document_id}")

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == int(current_user)
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # If using Temporal, get workflow status
    workflow_status = None
    if document.workflow_id and settings.ENABLE_TEMPORAL_WORKFLOWS:
        try:
            temporal_client = get_temporal_client()
            workflow_status = await temporal_client.get_workflow_status(document.workflow_id)
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")

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
        "workflow_status": workflow_status
    }
