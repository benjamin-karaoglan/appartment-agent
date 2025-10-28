"""Documents API routes."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import os
import uuid
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

router = APIRouter()


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
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Upload a document for analysis."""

    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed"
        )

    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    file_size = len(content)

    # Create document record
    document = Document(
        user_id=int(current_user),
        property_id=property_id,
        filename=file.filename,
        file_path=file_path,
        file_type=file_ext,
        document_category=document_category,
        file_size=file_size
    )

    db.add(document)
    db.commit()
    db.refresh(document)

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
