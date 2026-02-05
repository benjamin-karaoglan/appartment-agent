"""
Document Parser - Multimodal document parsing using Gemini.

Handles PDF-to-image conversion and AI analysis for property documents.
"""

import base64
import fitz  # PyMuPDF
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentSummary
from app.models.user import User
from app.services.storage import get_storage_service

logger = logging.getLogger(__name__)


class DocumentParser:
    """Multimodal document parser using Gemini vision capabilities."""

    def __init__(self):
        """Initialize Gemini client."""
        logger.info("Initializing DocumentParser")

        self.use_vertexai = settings.GEMINI_USE_VERTEXAI
        self.model = settings.GEMINI_LLM_MODEL
        self.project = settings.GOOGLE_CLOUD_PROJECT
        self.location = settings.GOOGLE_CLOUD_LOCATION

        if self.use_vertexai:
            if not self.project:
                raise RuntimeError("GOOGLE_CLOUD_PROJECT required for Vertex AI")
            self.client = genai.Client(vertexai=True, project=self.project, location=self.location)
        else:
            api_key = settings.GOOGLE_CLOUD_API_KEY
            if not api_key:
                raise RuntimeError("GOOGLE_CLOUD_API_KEY required")
            self.client = genai.Client(api_key=api_key)

        logger.info(f"Using model: {self.model}")

    def _extract_text(self, response) -> str:
        """Extract text from Gemini response."""
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []
        return "\n".join(p.text for p in parts if getattr(p, "text", None)).strip()

    def _get_config(self, max_tokens: int = 4096, temperature: float = 0.1) -> types.GenerateContentConfig:
        """Get generation configuration."""
        return types.GenerateContentConfig(temperature=temperature, top_p=0.95, max_output_tokens=max_tokens)

    def _extract_json(self, response_text: str) -> str:
        """Extract JSON from response text."""
        if "```json" in response_text:
            return response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            return response_text.split("```")[1].split("```")[0].strip()
        else:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            if json_start != -1 and json_end > json_start:
                return response_text[json_start:json_end + 1].strip()
        return response_text

    def pdf_to_images_base64(self, pdf_path: str, max_pages: int = 20, storage_key: str = None, storage_bucket: str = None) -> List[Dict[str, str]]:
        """
        Convert PDF pages to base64 images.
        
        Args:
            pdf_path: Local file path OR storage URI (storage://bucket/key)
            max_pages: Maximum number of pages to convert
            storage_key: Optional storage key for cloud storage
            storage_bucket: Optional storage bucket name
        """
        try:
            # Check if we need to download from storage
            if storage_key or (pdf_path and pdf_path.startswith("storage://")):
                logger.info(f"Downloading PDF from storage: {storage_key or pdf_path}")
                storage = get_storage_service()
                
                # Use storage_key if provided, otherwise extract from path
                key = storage_key
                bucket = storage_bucket
                
                if not key and pdf_path.startswith("storage://"):
                    # Parse storage://bucket/key format
                    parts = pdf_path.replace("storage://", "").split("/", 1)
                    if len(parts) == 2:
                        bucket = parts[0] if not bucket else bucket
                        key = parts[1]
                    else:
                        raise ValueError(f"Invalid storage path format: {pdf_path}")
                
                # Download file bytes from storage
                pdf_bytes = storage.download_file(key, bucket)
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                logger.info(f"Downloaded and opened PDF from storage: {key}")
            else:
                # Local file path
                doc = fitz.open(pdf_path)
            
            images = []

            for page_num in range(min(len(doc), max_pages)):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
                img_bytes = pix.tobytes("png")
                images.append({
                    "page_num": page_num + 1,
                    "base64_image": base64.b64encode(img_bytes).decode('utf-8')
                })

            doc.close()
            logger.info(f"Converted {len(images)} pages from {pdf_path or storage_key}")
            return images

        except Exception as e:
            logger.error(f"PDF conversion error: {e}")
            return []

    async def _analyze_with_images(self, images: List[Dict], prompt: str) -> Dict[str, Any]:
        """Send images with prompt to Gemini."""
        parts = []
        for img_data in images:
            img_bytes = base64.b64decode(img_data["base64_image"])
            parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        parts.append(types.Part.from_text(text=prompt))

        response = self.client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=parts)],
            config=self._get_config(),
        )

        response_text = self._extract_text(response)
        if not response_text:
            logger.warning("Empty response from AI model")
            raise ValueError("AI model returned empty response")

        json_text = self._extract_json(response_text)
        if not json_text or not json_text.strip():
            logger.warning(f"Could not extract JSON from response: {response_text[:500]}")
            raise ValueError("Could not extract JSON from AI response")

        return json.loads(json_text)

    async def parse_pv_ag_multimodal(self, pdf_path: str, storage_key: str = None, storage_bucket: str = None) -> Dict[str, Any]:
        """Parse PV d'AG using multimodal approach."""
        logger.info(f"Parsing PV d'AG: {pdf_path}, storage_key: {storage_key}")
        images = self.pdf_to_images_base64(pdf_path, max_pages=15, storage_key=storage_key, storage_bucket=storage_bucket)
        if not images:
            return {"error": "Could not extract images", "summary": "Failed to parse"}

        try:
            return await self._analyze_with_images(images, """Analyze this PV d'AG and return JSON:
{
    "meeting_date": "YYYY-MM-DD or null",
    "summary": "2-3 sentence summary",
    "key_insights": ["insight1", "insight2", "insight3"],
    "upcoming_works": [{"description": "...", "estimated_cost": 0, "timeline": "...", "urgency": "high/medium/low"}],
    "financial_health": {"annual_budget": 0, "reserves": 0, "outstanding_debts": 0, "health_status": "good/fair/poor"},
    "estimated_annual_cost": 0,
    "one_time_costs": [{"item": "...", "amount": 0, "timeline": "..."}],
    "risk_assessment": {"overall_risk": "low/medium/high", "risk_factors": [], "recommendations": []}
}""")
        except Exception as e:
            logger.error(f"PV d'AG parsing error: {e}")
            return {"error": str(e), "summary": "Failed to parse", "key_insights": []}

    async def parse_diagnostic_multimodal(self, pdf_path: str, subcategory: str, storage_key: str = None, storage_bucket: str = None) -> Dict[str, Any]:
        """Parse diagnostic document."""
        logger.info(f"Parsing diagnostic ({subcategory}): {pdf_path}, storage_key: {storage_key}")
        images = self.pdf_to_images_base64(pdf_path, max_pages=10, storage_key=storage_key, storage_bucket=storage_bucket)
        if not images:
            return {"error": "Could not extract images", "summary": "Failed to parse"}

        try:
            return await self._analyze_with_images(images, f"""Analyze this {subcategory} diagnostic and return JSON:
{{
    "diagnostic_date": "YYYY-MM-DD or null",
    "summary": "2-3 sentence summary",
    "key_insights": ["insight1", "insight2", "insight3"],
    "compliance_status": "compliant/non-compliant/needs-work",
    "issues_found": [{{"issue": "...", "severity": "critical/major/minor", "estimated_fix_cost": 0}}],
    "ratings": {{"dpe_rating": "A-G or null", "ges_rating": "A-G or null"}},
    "estimated_annual_cost": 0,
    "one_time_costs": [{{"item": "...", "amount": 0, "urgency": "high/medium/low"}}],
    "recommendations": []
}}""")
        except Exception as e:
            logger.error(f"Diagnostic parsing error: {e}")
            return {"error": str(e), "summary": "Failed to parse", "key_insights": []}

    async def parse_tax_charges_multimodal(self, pdf_path: str, category: str, storage_key: str = None, storage_bucket: str = None) -> Dict[str, Any]:
        """Parse tax or charges document."""
        logger.info(f"Parsing {category}: {pdf_path}, storage_key: {storage_key}")
        images = self.pdf_to_images_base64(pdf_path, max_pages=5, storage_key=storage_key, storage_bucket=storage_bucket)
        if not images:
            return {"error": "Could not extract images", "summary": "Failed to parse"}

        doc_type = "taxe foncière" if category == "taxe_fonciere" else "charges de copropriété"
        try:
            return await self._analyze_with_images(images, f"""Analyze this {doc_type} and return JSON:
{{
    "document_year": "YYYY",
    "summary": "2-3 sentence summary",
    "key_insights": ["insight1", "insight2"],
    "total_annual_amount": 0,
    "breakdown": {{}},
    "estimated_annual_cost": 0
}}""")
        except Exception as e:
            logger.error(f"Tax/charges parsing error: {e}")
            return {"error": str(e), "summary": "Failed to parse", "key_insights": []}

    async def parse_document(self, document: Document, db: Session) -> Document:
        """Parse a document and update the database record."""
        logger.info(f"Parsing document ID {document.id}, category: {document.document_category}, storage_key: {document.storage_key}")

        parsed_data = None
        # Pass storage_key and storage_bucket for cloud storage support
        storage_key = document.storage_key
        storage_bucket = document.storage_bucket
        
        if document.document_category == "pv_ag":
            parsed_data = await self.parse_pv_ag_multimodal(
                document.file_path, 
                storage_key=storage_key, 
                storage_bucket=storage_bucket
            )
        elif document.document_category == "diags":
            parsed_data = await self.parse_diagnostic_multimodal(
                document.file_path, 
                document.document_subcategory or "general",
                storage_key=storage_key,
                storage_bucket=storage_bucket
            )
        elif document.document_category in ["taxe_fonciere", "charges"]:
            parsed_data = await self.parse_tax_charges_multimodal(
                document.file_path, 
                document.document_category,
                storage_key=storage_key,
                storage_bucket=storage_bucket
            )

        if parsed_data and "error" not in parsed_data:
            document.is_analyzed = True
            document.parsed_at = datetime.utcnow()
            document.analysis_summary = parsed_data.get("summary", "")
            document.extracted_data = json.dumps(parsed_data)
            document.key_insights = parsed_data.get("key_insights", [])
            document.estimated_annual_cost = parsed_data.get("estimated_annual_cost")
            document.one_time_costs = parsed_data.get("one_time_costs", [])

            # Extract date
            for date_field in ["meeting_date", "diagnostic_date"]:
                if parsed_data.get(date_field):
                    try:
                        document.document_date = datetime.strptime(parsed_data[date_field], "%Y-%m-%d")
                        break
                    except:
                        pass

            # Increment user's documents analyzed count
            if document.user_id:
                user = db.query(User).filter(User.id == document.user_id).first()
                if user:
                    user.documents_analyzed_count = (user.documents_analyzed_count or 0) + 1

            db.commit()
            db.refresh(document)
            logger.info(f"Successfully parsed document ID {document.id}")
        else:
            document.is_analyzed = False
            document.analysis_summary = f"Failed: {parsed_data.get('error', 'Unknown')}" if parsed_data else "No data"
            db.commit()

        return document

    async def aggregate_pv_ag_summaries(self, property_id: int, db: Session) -> Optional[DocumentSummary]:
        """Aggregate all PV d'AG documents into one summary."""
        documents = db.query(Document).filter(
            Document.property_id == property_id,
            Document.document_category == "pv_ag",
            Document.is_analyzed == True
        ).all()

        if not documents:
            return None

        all_data = []
        for doc in documents:
            if doc.extracted_data:
                try:
                    all_data.append({"filename": doc.filename, "data": json.loads(doc.extracted_data)})
                except:
                    continue

        if not all_data:
            return None

        try:
            parts = [types.Part.from_text(text=f"""Synthesize these PV d'AG documents into JSON:
{json.dumps(all_data, default=str)[:15000]}

Return JSON:
{{
    "summary": "Overall summary",
    "key_findings": [],
    "copropriete_insights": {{}},
    "total_estimated_annual_cost": 0,
    "total_one_time_costs": 0,
    "cost_breakdown": {{}},
    "recommendations": []
}}""")]

            response = self.client.models.generate_content(
                model=self.model,
                contents=[types.Content(role="user", parts=parts)],
                config=self._get_config(),
            )
            result = json.loads(self._extract_json(self._extract_text(response)))

            summary = db.query(DocumentSummary).filter(
                DocumentSummary.property_id == property_id,
                DocumentSummary.category == "pv_ag"
            ).first()

            if not summary:
                summary = DocumentSummary(property_id=property_id, category="pv_ag")
                db.add(summary)

            summary.summary = result.get("summary")
            summary.key_findings = result.get("key_findings", [])
            summary.copropriete_insights = result.get("copropriete_insights", {})
            summary.total_estimated_annual_cost = result.get("total_estimated_annual_cost")
            summary.total_one_time_costs = result.get("total_one_time_costs")
            summary.cost_breakdown = result.get("cost_breakdown", {})
            summary.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(summary)
            return summary

        except Exception as e:
            logger.error(f"Aggregation error: {e}")
            return None

    async def aggregate_diagnostic_summaries(self, property_id: int, db: Session) -> Optional[DocumentSummary]:
        """Aggregate all diagnostic documents into one summary."""
        documents = db.query(Document).filter(
            Document.property_id == property_id,
            Document.document_category == "diags",
            Document.is_analyzed == True
        ).all()

        if not documents:
            return None

        all_data = []
        for doc in documents:
            if doc.extracted_data:
                try:
                    all_data.append({"subcategory": doc.document_subcategory, "data": json.loads(doc.extracted_data)})
                except:
                    continue

        if not all_data:
            return None

        try:
            parts = [types.Part.from_text(text=f"""Synthesize these diagnostics into JSON:
{json.dumps(all_data, default=str)[:15000]}

Return JSON:
{{
    "summary": "Overall summary",
    "key_findings": [],
    "diagnostic_issues": {{}},
    "total_estimated_annual_cost": 0,
    "total_one_time_costs": 0,
    "recommendations": []
}}""")]

            response = self.client.models.generate_content(
                model=self.model,
                contents=[types.Content(role="user", parts=parts)],
                config=self._get_config(),
            )
            result = json.loads(self._extract_json(self._extract_text(response)))

            summary = db.query(DocumentSummary).filter(
                DocumentSummary.property_id == property_id,
                DocumentSummary.category == "diags"
            ).first()

            if not summary:
                summary = DocumentSummary(property_id=property_id, category="diags")
                db.add(summary)

            summary.summary = result.get("summary")
            summary.key_findings = result.get("key_findings", [])
            summary.diagnostic_issues = result.get("diagnostic_issues", {})
            summary.total_estimated_annual_cost = result.get("total_estimated_annual_cost")
            summary.total_one_time_costs = result.get("total_one_time_costs")
            summary.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(summary)
            return summary

        except Exception as e:
            logger.error(f"Diagnostic aggregation error: {e}")
            return None


# Singleton
_instance: Optional[DocumentParser] = None


def get_document_parser() -> DocumentParser:
    """Get or create the DocumentParser singleton."""
    global _instance
    if _instance is None:
        _instance = DocumentParser()
    return _instance


# Backward compatibility
DocumentParsingService = DocumentParser
