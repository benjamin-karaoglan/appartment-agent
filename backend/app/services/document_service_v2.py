"""
Document parsing and analysis service with multimodal Claude API support.
Handles PDF extraction, AI analysis using Claude's vision capabilities.
"""

import base64
import fitz  # PyMuPDF
import json
import logging
import anthropic
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.document import Document, DocumentSummary

logger = logging.getLogger(__name__)


class DocumentParsingService:
    """Service for parsing and analyzing uploaded documents using Claude's multimodal capabilities."""

    def __init__(self):
        logger.info("Initializing DocumentParsingService")
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.ANTHROPIC_MODEL or "claude-3-haiku-20240307"
        logger.info(f"Using Claude model: {self.model}")

    def pdf_to_images_base64(self, pdf_path: str, max_pages: int = 20) -> List[Dict[str, str]]:
        """
        Convert PDF pages to base64-encoded images for multimodal analysis.

        Args:
            pdf_path: Path to the PDF file
            max_pages: Maximum number of pages to process

        Returns:
            List of dicts with 'page_num' and 'base64_image' keys
        """
        try:
            logger.info(f"Converting PDF to images: {pdf_path}")
            doc = fitz.open(pdf_path)
            images = []

            num_pages = min(len(doc), max_pages)
            logger.info(f"Processing {num_pages} pages from PDF")

            for page_num in range(num_pages):
                page = doc[page_num]
                # Render page to image (PNG format, 150 DPI for good quality)
                pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
                img_bytes = pix.tobytes("png")

                # Encode to base64
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')

                images.append({
                    "page_num": page_num + 1,
                    "base64_image": img_base64
                })

                logger.debug(f"Converted page {page_num + 1} to base64 image")

            doc.close()
            logger.info(f"Successfully converted {len(images)} pages to images")
            return images

        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}", exc_info=True)
            return []

    async def parse_pv_ag_multimodal(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parse PV d'AG using Claude's multimodal capabilities.
        Sends PDF pages as images to Claude for better accuracy.
        """
        logger.info(f"Parsing PV d'AG with multimodal approach: {pdf_path}")

        try:
            images = self.pdf_to_images_base64(pdf_path, max_pages=15)

            if not images:
                logger.error("Failed to extract images from PDF")
                raise Exception("Could not extract images from PDF")

            # Build multimodal content with images
            content = [
                {
                    "type": "text",
                    "text": """Analyze this French copropriété assembly meeting minutes (PV d'AG) and extract structured information.

Extract and return a JSON object with this exact structure:
{
    "meeting_date": "YYYY-MM-DD or null if not found",
    "summary": "2-3 sentence summary of the meeting",
    "key_insights": [
        "Most important point 1",
        "Most important point 2",
        "Most important point 3"
    ],
    "upcoming_works": [
        {
            "description": "Description of work",
            "estimated_cost": 12000,
            "timeline": "2025 or description",
            "urgency": "high/medium/low"
        }
    ],
    "coproprietaire_issues": {
        "payment_problems": ["List any copropriétaires not paying charges"],
        "disputes": ["List any conflicts or disputes mentioned"],
        "annoying_behaviors": ["List problematic behaviors if mentioned"]
    },
    "financial_health": {
        "annual_budget": 50000,
        "reserves": 20000,
        "outstanding_debts": 5000,
        "health_status": "good/fair/poor"
    },
    "estimated_annual_cost": 3000,
    "one_time_costs": [
        {"item": "Ravalement de façade", "amount": 50000, "timeline": "2025"},
        {"item": "Réfection toiture", "amount": 30000, "timeline": "2026"}
    ],
    "risk_assessment": {
        "overall_risk": "low/medium/high",
        "risk_factors": ["List specific risk factors"],
        "recommendations": ["List recommendations for buyer"]
    }
}

Be precise with numbers. If information is not found, use null or empty arrays."""
                }
            ]

            # Add images
            for img_data in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_data["base64_image"]
                    }
                })
                logger.debug(f"Added page {img_data['page_num']} to analysis")

            logger.info(f"Sending {len(images)} pages to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )

            response_text = message.content[0].text
            logger.debug(f"Claude response length: {len(response_text)} characters")

            # Extract JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                # No code blocks - try to find JSON object by looking for first { and last }
                json_start = response_text.find('{')
                json_end = response_text.rfind('}')
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    response_text = response_text[json_start:json_end+1].strip()

            result = json.loads(response_text)
            logger.info("Successfully parsed PV d'AG document")
            return result

        except Exception as e:
            logger.error(f"Error parsing PV d'AG: {e}", exc_info=True)
            return {
                "error": str(e),
                "summary": "Failed to parse document",
                "key_insights": [],
                "estimated_annual_cost": None,
                "one_time_costs": []
            }

    async def parse_diagnostic_multimodal(self, pdf_path: str, subcategory: str) -> Dict[str, Any]:
        """
        Parse diagnostic documents using Claude's multimodal capabilities.
        """
        logger.info(f"Parsing diagnostic ({subcategory}) with multimodal approach: {pdf_path}")

        diagnostic_prompts = {
            "dpe": "DPE (Diagnostic de Performance Énergétique) - energy performance",
            "amiante": "Diagnostic Amiante - asbestos detection",
            "plomb": "Diagnostic Plomb - lead detection",
            "termite": "Diagnostic Termite - termite infestation",
            "electric": "Diagnostic Électricité - electrical system",
            "gas": "Diagnostic Gaz - gas installation"
        }

        diagnostic_type = diagnostic_prompts.get(subcategory, "diagnostic document")

        try:
            images = self.pdf_to_images_base64(pdf_path, max_pages=10)

            if not images:
                logger.error("Failed to extract images from PDF")
                raise Exception("Could not extract images from PDF")

            content = [
                {
                    "type": "text",
                    "text": f"""Analyze this French property {diagnostic_type} and extract structured information.

Extract and return a JSON object with this exact structure:
{{
    "diagnostic_date": "YYYY-MM-DD or null",
    "summary": "2-3 sentence summary of diagnostic results",
    "key_insights": [
        "Most critical finding 1",
        "Most critical finding 2",
        "Most critical finding 3"
    ],
    "compliance_status": "compliant/non-compliant/needs-work",
    "issues_found": [
        {{
            "issue": "Description of issue",
            "severity": "critical/major/minor",
            "location": "Where in property",
            "estimated_fix_cost": 5000
        }}
    ],
    "ratings": {{
        "dpe_rating": "A-G or null",
        "ges_rating": "A-G or null",
        "energy_consumption_kwh": 250 or null
    }},
    "estimated_annual_cost": 0,
    "one_time_costs": [
        {{"item": "Removing asbestos", "amount": 15000, "urgency": "high"}},
        {{"item": "Electrical panel upgrade", "amount": 3000, "urgency": "medium"}}
    ],
    "recommendations": [
        "Recommendation 1",
        "Recommendation 2"
    ]
}}

Be precise with ratings and costs. If information is not found, use null or empty arrays."""
                }
            ]

            # Add images
            for img_data in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_data["base64_image"]
                    }
                })

            logger.info(f"Sending {len(images)} pages to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )

            response_text = message.content[0].text
            logger.info(f"✅ Received Claude response - length: {len(response_text)} characters")
            logger.info(f"📄 Claude raw response (first 500 chars): {response_text[:500]}")

            # Extract JSON from response
            original_response = response_text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
                logger.info("Extracted JSON from ```json``` code block")
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
                logger.info("Extracted JSON from ``` code block")
            else:
                # No code blocks - try to find JSON object by looking for first { and last }
                json_start = response_text.find('{')
                json_end = response_text.rfind('}')
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    response_text = response_text[json_start:json_end+1].strip()
                    logger.info("Extracted JSON by finding { } boundaries")

            logger.info(f"📊 Cleaned JSON (first 500 chars): {response_text[:500]}")

            try:
                result = json.loads(response_text)
                logger.info(f"✅ Successfully parsed {subcategory} diagnostic - keys: {list(result.keys())}")
                logger.info(f"📝 Summary: {result.get('summary', 'N/A')}")
                logger.info(f"🔍 Key insights count: {len(result.get('key_insights', []))}")
                logger.info(f"💰 Estimated annual cost: {result.get('estimated_annual_cost')}")
                logger.info(f"📋 Full parsed result: {json.dumps(result, indent=2, default=str)}")
                return result
            except json.JSONDecodeError as je:
                logger.error(f"❌ JSON parsing failed: {je}")
                logger.error(f"Failed JSON text: {response_text}")
                logger.error(f"Original response: {original_response}")
                raise

        except Exception as e:
            logger.error(f"❌ Error parsing diagnostic: {e}", exc_info=True)
            return {
                "error": str(e),
                "summary": "Failed to parse diagnostic",
                "key_insights": [],
                "compliance_status": "unknown",
                "estimated_annual_cost": None,
                "one_time_costs": []
            }

    async def parse_tax_charges_multimodal(self, pdf_path: str, category: str) -> Dict[str, Any]:
        """
        Parse tax foncière or charges documents using multimodal approach.
        """
        logger.info(f"Parsing tax/charges ({category}) with multimodal approach: {pdf_path}")

        doc_type = "taxe foncière" if category == "taxe_fonciere" else "charges de copropriété"

        try:
            images = self.pdf_to_images_base64(pdf_path, max_pages=5)

            if not images:
                logger.error("Failed to extract images from PDF")
                raise Exception("Could not extract images from PDF")

            content = [
                {
                    "type": "text",
                    "text": f"""Analyze this French property {doc_type} document and extract structured information.

Extract and return a JSON object with this exact structure:
{{
    "document_year": "2024 or year mentioned",
    "summary": "2-3 sentence summary",
    "key_insights": [
        "Key finding 1",
        "Key finding 2"
    ],
    "total_annual_amount": 2500,
    "breakdown": {{
        "base_amount": 2000,
        "additional_fees": 300,
        "taxes": 200
    }},
    "payment_schedule": [
        {{"date": "2024-03-15", "amount": 1250}},
        {{"date": "2024-09-15", "amount": 1250}}
    ],
    "estimated_annual_cost": 2500,
    "trends": {{
        "vs_previous_year": "+5% or -3% or description",
        "projection_next_year": 2625
    }}
}}

Be precise with amounts. If information is not found, use null."""
                }
            ]

            # Add images
            for img_data in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_data["base64_image"]
                    }
                })

            logger.info(f"Sending {len(images)} pages to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )

            response_text = message.content[0].text

            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                # No code blocks - try to find JSON object by looking for first { and last }
                json_start = response_text.find('{')
                json_end = response_text.rfind('}')
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    response_text = response_text[json_start:json_end+1].strip()

            result = json.loads(response_text)
            logger.info("Successfully parsed tax/charges document")
            return result

        except Exception as e:
            logger.error(f"Error parsing tax/charges: {e}", exc_info=True)
            return {
                "error": str(e),
                "summary": "Failed to parse document",
                "key_insights": [],
                "estimated_annual_cost": None
            }

    async def parse_document(self, document: Document, db: Session) -> Document:
        """
        Main method to parse a document based on its category using multimodal Claude API.
        Updates the document record with extracted data.
        """
        logger.info(f"Starting document parsing for document ID {document.id}, category: {document.document_category}")

        try:
            # Parse based on category using multimodal approach
            parsed_data = None

            if document.document_category == "pv_ag":
                parsed_data = await self.parse_pv_ag_multimodal(document.file_path)

            elif document.document_category == "diags":
                subcategory = document.document_subcategory or "general"
                parsed_data = await self.parse_diagnostic_multimodal(document.file_path, subcategory)

            elif document.document_category in ["taxe_fonciere", "charges"]:
                parsed_data = await self.parse_tax_charges_multimodal(document.file_path, document.document_category)

            else:
                logger.warning(f"Unknown document category: {document.document_category}")
                document.is_analyzed = False
                document.analysis_summary = f"Unsupported document category: {document.document_category}"
                db.commit()
                return document

            logger.info(f"📊 Parsed data received for document {document.id}: {parsed_data is not None}")
            if parsed_data:
                logger.info(f"📋 Parsed data keys: {list(parsed_data.keys())}")
                logger.info(f"❌ Error in parsed data: {'error' in parsed_data}")

            if parsed_data and "error" not in parsed_data:
                # Update document with parsed data
                document.is_analyzed = True
                document.parsed_at = datetime.utcnow()
                document.analysis_summary = parsed_data.get("summary", "")
                document.extracted_data = json.dumps(parsed_data)
                document.key_insights = parsed_data.get("key_insights", [])
                document.estimated_annual_cost = parsed_data.get("estimated_annual_cost")
                document.one_time_costs = parsed_data.get("one_time_costs", [])

                logger.info(f"💾 Updating document {document.id} with:")
                logger.info(f"  - is_analyzed: {document.is_analyzed}")
                logger.info(f"  - analysis_summary: {document.analysis_summary[:100]}...")
                logger.info(f"  - key_insights: {document.key_insights}")
                logger.info(f"  - estimated_annual_cost: {document.estimated_annual_cost}")
                logger.info(f"  - one_time_costs: {document.one_time_costs}")

                # Try to extract document date
                if "meeting_date" in parsed_data and parsed_data["meeting_date"]:
                    try:
                        document.document_date = datetime.strptime(
                            parsed_data["meeting_date"], "%Y-%m-%d"
                        )
                    except Exception as date_error:
                        logger.warning(f"Could not parse meeting_date: {date_error}")
                elif "diagnostic_date" in parsed_data and parsed_data["diagnostic_date"]:
                    try:
                        document.document_date = datetime.strptime(
                            parsed_data["diagnostic_date"], "%Y-%m-%d"
                        )
                        logger.info(f"📅 Extracted diagnostic date: {document.document_date}")
                    except Exception as date_error:
                        logger.warning(f"Could not parse diagnostic_date: {date_error}")

                db.commit()
                db.refresh(document)
                logger.info(f"✅ Successfully parsed and saved document ID {document.id}")
                logger.info(f"📄 Document after save - is_analyzed: {document.is_analyzed}, summary length: {len(document.analysis_summary) if document.analysis_summary else 0}")
            else:
                error_msg = parsed_data.get("error", "Unknown error") if parsed_data else "No data returned"
                logger.error(f"Parsing failed for document ID {document.id}: {error_msg}")
                document.is_analyzed = False
                document.analysis_summary = f"Failed to parse: {error_msg}"
                db.commit()

            return document

        except Exception as e:
            logger.error(f"Error parsing document {document.id}: {e}", exc_info=True)
            document.is_analyzed = False
            document.analysis_summary = f"Error: {str(e)}"
            db.commit()
            return document

    async def aggregate_pv_ag_summaries(
        self,
        property_id: int,
        db: Session
    ) -> Optional[DocumentSummary]:
        """
        Aggregate all PV d'AG documents for a property into one comprehensive summary.
        """
        logger.info(f"Aggregating PV d'AG summaries for property ID {property_id}")

        documents = db.query(Document).filter(
            Document.property_id == property_id,
            Document.document_category == "pv_ag",
            Document.is_analyzed == True
        ).all()

        if not documents:
            logger.info(f"No PV d'AG documents found for property ID {property_id}")
            return None

        logger.info(f"Found {len(documents)} PV d'AG documents to aggregate")

        # Compile all extracted data
        all_data = []
        for doc in documents:
            if doc.extracted_data:
                try:
                    data = json.loads(doc.extracted_data)
                    all_data.append({
                        "filename": doc.filename,
                        "date": doc.document_date,
                        "data": data
                    })
                except Exception as e:
                    logger.warning(f"Could not parse extracted_data for document {doc.id}: {e}")
                    continue

        if not all_data:
            logger.warning("No valid extracted data found in documents")
            return None

        # Create comprehensive prompt for Claude
        prompt = f"""Analyze these {len(all_data)} PV d'AG (copropriété assembly minutes) and create a comprehensive summary.

Documents:
{json.dumps(all_data, indent=2, default=str)[:20000]}

Create a comprehensive analysis in JSON format:
{{
    "summary": "Overall 3-4 sentence summary covering the most important points across all meetings",
    "key_findings": [
        "Most critical finding 1",
        "Most critical finding 2",
        "Most critical finding 3",
        "Most critical finding 4",
        "Most critical finding 5"
    ],
    "copropriete_insights": {{
        "payment_behavior": "Overall assessment of copropriétaires paying their charges",
        "problematic_owners": ["List any repeatedly problematic owners if mentioned"],
        "disputes_summary": "Summary of any ongoing disputes",
        "financial_health": "Overall financial health assessment",
        "management_quality": "Assessment of syndic/management quality"
    }},
    "upcoming_works": [
        {{
            "work": "Description",
            "estimated_cost": 50000,
            "timeline": "2025-2026",
            "urgency": "high/medium/low",
            "status": "planned/voted/in-progress"
        }}
    ],
    "cost_breakdown": {{
        "immediate_costs": 10000,
        "short_term_1_2_years": 50000,
        "medium_term_3_5_years": 100000,
        "annual_charges_trend": "increasing/stable/decreasing"
    }},
    "total_estimated_annual_cost": 3500,
    "total_one_time_costs": 150000,
    "risk_assessment": {{
        "overall_risk": "low/medium/high",
        "key_risks": ["Risk 1", "Risk 2"],
        "red_flags": ["Any serious concerns"],
        "positive_points": ["Good aspects"]
    }},
    "recommendations": [
        "Actionable recommendation 1",
        "Actionable recommendation 2",
        "Actionable recommendation 3"
    ]
}}

Focus on actionable insights for a potential buyer."""

        try:
            logger.info("Sending aggregation request to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = message.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                # No code blocks - try to find JSON object by looking for first { and last }
                json_start = response_text.find('{')
                json_end = response_text.rfind('}')
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    response_text = response_text[json_start:json_end+1].strip()

            result = json.loads(response_text)

            # Create or update DocumentSummary
            summary = db.query(DocumentSummary).filter(
                DocumentSummary.property_id == property_id,
                DocumentSummary.category == "pv_ag"
            ).first()

            if not summary:
                summary = DocumentSummary(
                    property_id=property_id,
                    category="pv_ag"
                )
                db.add(summary)
                logger.info("Created new DocumentSummary")
            else:
                logger.info("Updating existing DocumentSummary")

            summary.summary = result.get("summary")
            summary.key_findings = result.get("key_findings", [])
            summary.copropriete_insights = result.get("copropriete_insights", {})
            summary.total_estimated_annual_cost = result.get("total_estimated_annual_cost")
            summary.total_one_time_costs = result.get("total_one_time_costs")
            summary.cost_breakdown = result.get("cost_breakdown", {})
            summary.last_document_count = len(documents)
            summary.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(summary)

            logger.info(f"Successfully aggregated PV d'AG summaries for property ID {property_id}")
            return summary

        except Exception as e:
            logger.error(f"Error aggregating PV d'AG summaries: {e}", exc_info=True)
            return None

    async def aggregate_diagnostic_summaries(
        self,
        property_id: int,
        db: Session
    ) -> Optional[DocumentSummary]:
        """
        Aggregate all diagnostic documents into one summary.
        """
        logger.info(f"Aggregating diagnostic summaries for property ID {property_id}")

        documents = db.query(Document).filter(
            Document.property_id == property_id,
            Document.document_category == "diags",
            Document.is_analyzed == True
        ).all()

        if not documents:
            logger.info(f"No diagnostic documents found for property ID {property_id}")
            return None

        logger.info(f"Found {len(documents)} diagnostic documents to aggregate")

        all_data = []
        for doc in documents:
            if doc.extracted_data:
                try:
                    data = json.loads(doc.extracted_data)
                    all_data.append({
                        "subcategory": doc.document_subcategory,
                        "filename": doc.filename,
                        "data": data
                    })
                except Exception as e:
                    logger.warning(f"Could not parse extracted_data for document {doc.id}: {e}")
                    continue

        if not all_data:
            logger.warning("No valid extracted data found in documents")
            return None

        prompt = f"""Analyze these diagnostic documents and create a comprehensive summary.

Diagnostics:
{json.dumps(all_data, indent=2, default=str)[:20000]}

Create JSON:
{{
    "summary": "Overall summary of property condition based on all diagnostics",
    "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
    "diagnostic_issues": {{
        "critical_issues": ["List critical issues requiring immediate attention"],
        "major_issues": ["List major issues to address soon"],
        "minor_issues": ["List minor issues"],
        "compliance_status": "Overall compliance status"
    }},
    "total_estimated_annual_cost": 500,
    "total_one_time_costs": 25000,
    "cost_breakdown": {{
        "immediate_critical": 15000,
        "short_term": 10000,
        "maintenance": 500
    }},
    "recommendations": ["Recommendation 1", "Recommendation 2"]
}}"""

        try:
            logger.info("Sending diagnostic aggregation request to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                # No code blocks - try to find JSON object by looking for first { and last }
                json_start = response_text.find('{')
                json_end = response_text.rfind('}')
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    response_text = response_text[json_start:json_end+1].strip()

            result = json.loads(response_text)

            summary = db.query(DocumentSummary).filter(
                DocumentSummary.property_id == property_id,
                DocumentSummary.category == "diags"
            ).first()

            if not summary:
                summary = DocumentSummary(
                    property_id=property_id,
                    category="diags"
                )
                db.add(summary)
                logger.info("Created new diagnostic DocumentSummary")
            else:
                logger.info("Updating existing diagnostic DocumentSummary")

            summary.summary = result.get("summary")
            summary.key_findings = result.get("key_findings", [])
            summary.diagnostic_issues = result.get("diagnostic_issues", {})
            summary.total_estimated_annual_cost = result.get("total_estimated_annual_cost")
            summary.total_one_time_costs = result.get("total_one_time_costs")
            summary.cost_breakdown = result.get("cost_breakdown", {})
            summary.last_document_count = len(documents)
            summary.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(summary)

            logger.info(f"Successfully aggregated diagnostic summaries for property ID {property_id}")
            return summary

        except Exception as e:
            logger.error(f"Error aggregating diagnostic summaries: {e}", exc_info=True)
            return None
