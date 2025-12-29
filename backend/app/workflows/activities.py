"""
Temporal activities for document processing.
Activities are the actual work units executed by Temporal workers.
"""

import logging
import hashlib
import json
import fitz  # PyMuPDF
from io import BytesIO
from datetime import datetime
from typing import Dict, Any, List
from temporalio import activity

from app.core.database import SessionLocal
from app.models.document import Document
from app.services.minio_service import get_minio_service
from app.services.langchain_service import get_langchain_service

logger = logging.getLogger(__name__)


@activity.defn(name="download_from_minio")
async def download_from_minio(minio_key: str) -> bytes:
    """
    Download a file from MinIO.

    Args:
        minio_key: The object key in MinIO

    Returns:
        Binary file data
    """
    logger.info(f"Activity: Downloading file from MinIO: {minio_key}")
    minio_service = get_minio_service()
    file_data = minio_service.download_file(minio_key)
    logger.info(f"Downloaded {len(file_data)} bytes from MinIO")
    return file_data


@activity.defn(name="pdf_to_images")
async def pdf_to_images(file_data: bytes) -> List[str]:
    """
    Convert PDF pages to base64-encoded images.

    Args:
        file_data: Binary PDF data

    Returns:
        List of base64-encoded PNG images
    """
    logger.info("Activity: Converting PDF to images")
    images_base64 = []

    try:
        pdf_document = fitz.open(stream=file_data, filetype="pdf")

        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)

            # Render at 150 DPI for good quality
            mat = fitz.Matrix(150/72, 150/72)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert to PNG bytes
            img_bytes = pix.tobytes("png")

            # Base64 encode
            import base64
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            images_base64.append(img_base64)

            logger.info(f"Converted page {page_num + 1}/{len(pdf_document)}")

        pdf_document.close()
        logger.info(f"PDF conversion complete: {len(images_base64)} pages")
        return images_base64

    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        raise


@activity.defn(name="analyze_with_langchain")
async def analyze_with_langchain(
    images_base64: List[str],
    document_id: int,
    document_type: str
) -> Dict[str, Any]:
    """
    Analyze document using LangChain and Claude vision.

    Args:
        images_base64: List of base64-encoded images
        document_id: Database ID of the document
        document_type: Type of document (pv_ag, diagnostic, etc.)

    Returns:
        Analysis result dict
    """
    logger.info(f"Activity: Analyzing document {document_id} ({document_type}) with LangChain")

    langchain_service = get_langchain_service()

    # Get appropriate prompt template based on document type
    prompt_template = _get_prompt_for_document_type(document_type)

    # Analyze
    result = langchain_service.analyze_document_with_vision(
        images_base64=images_base64,
        prompt_template=prompt_template,
        document_type=document_type
    )

    logger.info(f"Analysis complete for document {document_id}")
    return result


@activity.defn(name="update_document_status")
async def update_document_status(
    document_id: int,
    status: str,
    error: str = None
) -> None:
    """
    Update document processing status in database.

    Args:
        document_id: Database ID of the document
        status: New status (pending, processing, completed, failed)
        error: Error message if status is failed
    """
    logger.info(f"Activity: Updating document {document_id} status to {status}")

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return

        document.processing_status = status

        if status == "processing":
            document.processing_started_at = datetime.utcnow()
        elif status in ("completed", "failed"):
            document.processing_completed_at = datetime.utcnow()

        if error:
            document.processing_error = error

        db.commit()
        logger.info(f"Document {document_id} status updated to {status}")

    except Exception as e:
        logger.error(f"Error updating document status: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@activity.defn(name="save_analysis_results")
async def save_analysis_results(
    document_id: int,
    analysis_result: Dict[str, Any]
) -> None:
    """
    Save analysis results to database.

    Args:
        document_id: Database ID of the document
        analysis_result: Analysis result from LangChain
    """
    logger.info(f"Activity: Saving analysis results for document {document_id}")

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return

        # Extract JSON from response
        response_text = analysis_result["response"]

        # Parse JSON (with fallback extraction)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        else:
            # No code blocks - try to find JSON object
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end+1].strip()

        parsed_data = json.loads(response_text)

        # Update document fields
        document.is_analyzed = True
        document.parsed_at = datetime.utcnow()
        document.extracted_data = json.dumps(parsed_data)

        # Update LangChain metadata
        document.langchain_model = analysis_result.get("model")
        document.langchain_tokens_used = analysis_result.get("tokens_used", 0)
        document.langchain_cost = analysis_result.get("estimated_cost", 0.0)

        # Extract summary and insights
        if "summary" in parsed_data:
            document.analysis_summary = parsed_data["summary"]

        if "key_insights" in parsed_data:
            document.key_insights = parsed_data["key_insights"]

        # Extract cost estimates
        if "estimated_annual_cost" in parsed_data:
            document.estimated_annual_cost = float(parsed_data["estimated_annual_cost"])

        if "one_time_costs" in parsed_data:
            document.one_time_costs = parsed_data["one_time_costs"]

        db.commit()
        logger.info(f"Analysis results saved for document {document_id}")

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from analysis: {e}")
        logger.error(f"Response text: {response_text[:500]}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error saving analysis results: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@activity.defn(name="calculate_file_hash")
async def calculate_file_hash(file_data: bytes) -> str:
    """
    Calculate SHA-256 hash of file data.

    Args:
        file_data: Binary file data

    Returns:
        Hex-encoded SHA-256 hash
    """
    logger.info("Activity: Calculating file hash")
    file_hash = hashlib.sha256(file_data).hexdigest()
    logger.info(f"File hash: {file_hash}")
    return file_hash


def _get_prompt_for_document_type(document_type: str) -> str:
    """Get appropriate prompt template for document type."""
    prompts = {
        "pv_ag": """Analyze this PV d'AG (copropriété general assembly minutes) and extract:
- Meeting date
- Key decisions made
- Upcoming works and their estimated costs
- Any issues with copropriétaires (payment issues, disputes)
- Charges and fees mentioned
- Important deadlines

Return a JSON object with these fields:
{
  "summary": "Brief summary of the meeting",
  "key_insights": ["insight 1", "insight 2"],
  "estimated_annual_cost": 1234.56,
  "one_time_costs": [{"description": "Work description", "amount": 1000}],
  "meeting_date": "2024-01-15",
  "decisions": ["decision 1", "decision 2"],
  "upcoming_works": [{"description": "Work", "cost": 5000, "timeline": "Q2 2024"}]
}""",

        "diagnostic": """Analyze this diagnostic report and extract:
- Type of diagnostic (DPE, amiante, plomb, termites, electric, gas)
- Date of the diagnostic
- Overall result/rating
- Any issues or non-compliances found
- Recommendations
- Estimated costs for remediation

Return a JSON object with these fields:
{
  "summary": "Brief summary",
  "key_insights": ["insight 1", "insight 2"],
  "diagnostic_type": "DPE",
  "diagnostic_date": "2024-01-15",
  "rating": "C",
  "issues_found": ["issue 1", "issue 2"],
  "estimated_annual_cost": 0,
  "one_time_costs": [{"description": "Remediation", "amount": 2000}]
}""",

        "taxe_fonciere": """Analyze this taxe foncière document and extract:
- Year
- Total amount
- Property value (valeur cadastrale)
- Any exemptions or reductions

Return a JSON object with these fields:
{
  "summary": "Brief summary",
  "year": 2024,
  "total_amount": 1234.56,
  "property_value": 50000,
  "estimated_annual_cost": 1234.56,
  "key_insights": ["insight 1"]
}""",

        "charges": """Analyze this charges/copropriété fees document and extract:
- Period covered
- Total charges
- Breakdown by category (if available)
- Any special assessments

Return a JSON object with these fields:
{
  "summary": "Brief summary",
  "period": "2024",
  "total_charges": 2400,
  "estimated_annual_cost": 2400,
  "breakdown": {"heating": 1000, "maintenance": 800, "other": 600},
  "key_insights": ["insight 1"]
}"""
    }

    return prompts.get(document_type, prompts["diagnostic"])
