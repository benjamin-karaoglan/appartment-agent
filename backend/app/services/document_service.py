"""
Document parsing and analysis service.
Handles PDF extraction, AI analysis, and summarization.
"""

import fitz  # PyMuPDF
import json
import anthropic
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.document import Document, DocumentSummary


class DocumentParsingService:
    """Service for parsing and analyzing uploaded documents."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.ANTHROPIC_MODEL or "claude-3-haiku-20240307"

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF file."""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return ""

    async def parse_pv_ag(self, document_text: str) -> Dict[str, Any]:
        """
        Parse PV d'AG (Assembly General Meeting Minutes).

        Extracts:
        - Meeting date and attendees
        - Decisions made
        - Upcoming works and costs
        - Copropriétaire behavior and payment issues
        - Budget and financial health
        """

        prompt = f"""Analyze this French copropriété assembly meeting minutes (PV d'AG) and extract structured information.

Document text:
{document_text[:15000]}  # Limit to avoid token limits

Extract and return a JSON object with this exact structure:
{{
    "meeting_date": "YYYY-MM-DD or null if not found",
    "summary": "2-3 sentence summary of the meeting",
    "key_insights": [
        "Most important point 1",
        "Most important point 2",
        "Most important point 3"
    ],
    "upcoming_works": [
        {{
            "description": "Description of work",
            "estimated_cost": 12000,
            "timeline": "2025 or description",
            "urgency": "high/medium/low"
        }}
    ],
    "coproprietaire_issues": {{
        "payment_problems": ["List any copropriétaires not paying charges"],
        "disputes": ["List any conflicts or disputes mentioned"],
        "annoying_behaviors": ["List problematic behaviors if mentioned"]
    }},
    "financial_health": {{
        "annual_budget": 50000,
        "reserves": 20000,
        "outstanding_debts": 5000,
        "health_status": "good/fair/poor"
    }},
    "estimated_annual_cost": 3000,
    "one_time_costs": [
        {{"item": "Ravalement de façade", "amount": 50000, "timeline": "2025"}},
        {{"item": "Réfection toiture", "amount": 30000, "timeline": "2026"}}
    ],
    "risk_assessment": {{
        "overall_risk": "low/medium/high",
        "risk_factors": ["List specific risk factors"],
        "recommendations": ["List recommendations for buyer"]
    }}
}}

Be precise with numbers. If information is not found, use null or empty arrays."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = message.content[0].text
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            result = json.loads(response_text)
            return result
        except Exception as e:
            print(f"Error parsing PV d'AG: {e}")
            return {
                "error": str(e),
                "summary": "Failed to parse document",
                "key_insights": [],
                "estimated_annual_cost": None,
                "one_time_costs": []
            }

    async def parse_diagnostic(self, document_text: str, subcategory: str) -> Dict[str, Any]:
        """
        Parse diagnostic documents (DPE, amiante, plomb, termite, electric, gas).

        Extracts:
        - Diagnostic results
        - Compliance status
        - Required remediation work
        - Costs for fixing issues
        """

        diagnostic_prompts = {
            "dpe": "DPE (Diagnostic de Performance Énergétique) - energy performance",
            "amiante": "Diagnostic Amiante - asbestos detection",
            "plomb": "Diagnostic Plomb - lead detection",
            "termite": "Diagnostic Termite - termite infestation",
            "electric": "Diagnostic Électricité - electrical system",
            "gas": "Diagnostic Gaz - gas installation"
        }

        diagnostic_type = diagnostic_prompts.get(subcategory, "diagnostic document")

        prompt = f"""Analyze this French property {diagnostic_type} and extract structured information.

Document text:
{document_text[:15000]}

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

        try:
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

            result = json.loads(response_text)
            return result
        except Exception as e:
            print(f"Error parsing diagnostic: {e}")
            return {
                "error": str(e),
                "summary": "Failed to parse diagnostic",
                "key_insights": [],
                "compliance_status": "unknown",
                "estimated_annual_cost": None,
                "one_time_costs": []
            }

    async def parse_tax_charges(self, document_text: str, category: str) -> Dict[str, Any]:
        """
        Parse tax foncière or charges documents.

        Extracts:
        - Annual amounts
        - Breakdown by category
        - Payment schedule
        """

        doc_type = "taxe foncière" if category == "taxe_fonciere" else "charges de copropriété"

        prompt = f"""Analyze this French property {doc_type} document and extract structured information.

Document text:
{document_text[:15000]}

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

        try:
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

            result = json.loads(response_text)
            return result
        except Exception as e:
            print(f"Error parsing tax/charges: {e}")
            return {
                "error": str(e),
                "summary": "Failed to parse document",
                "key_insights": [],
                "estimated_annual_cost": None
            }

    async def parse_document(self, document: Document, db: Session) -> Document:
        """
        Main method to parse a document based on its category.
        Updates the document record with extracted data.
        """
        try:
            # Extract text from PDF
            text = self.extract_text_from_pdf(document.file_path)

            if not text or len(text) < 50:
                document.is_analyzed = False
                document.analysis_summary = "Failed to extract text from document"
                db.commit()
                return document

            # Parse based on category
            parsed_data = None

            if document.document_category == "pv_ag":
                parsed_data = await self.parse_pv_ag(text)

            elif document.document_category == "diags":
                subcategory = document.document_subcategory or "general"
                parsed_data = await self.parse_diagnostic(text, subcategory)

            elif document.document_category in ["taxe_fonciere", "charges"]:
                parsed_data = await self.parse_tax_charges(text, document.document_category)

            if parsed_data:
                # Update document with parsed data
                document.is_analyzed = True
                document.parsed_at = datetime.utcnow()
                document.analysis_summary = parsed_data.get("summary", "")
                document.extracted_data = json.dumps(parsed_data)
                document.key_insights = parsed_data.get("key_insights", [])
                document.estimated_annual_cost = parsed_data.get("estimated_annual_cost")
                document.one_time_costs = parsed_data.get("one_time_costs", [])

                # Try to extract document date
                if "meeting_date" in parsed_data and parsed_data["meeting_date"]:
                    try:
                        document.document_date = datetime.strptime(
                            parsed_data["meeting_date"], "%Y-%m-%d"
                        )
                    except:
                        pass
                elif "diagnostic_date" in parsed_data and parsed_data["diagnostic_date"]:
                    try:
                        document.document_date = datetime.strptime(
                            parsed_data["diagnostic_date"], "%Y-%m-%d"
                        )
                    except:
                        pass

                db.commit()

            return document

        except Exception as e:
            print(f"Error parsing document {document.id}: {e}")
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

        Analyzes copropriétaire behavior, upcoming works, payment issues, etc.
        """
        # Get all PV d'AG documents for this property
        documents = db.query(Document).filter(
            Document.property_id == property_id,
            Document.document_category == "pv_ag",
            Document.is_analyzed == True
        ).all()

        if not documents:
            return None

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
                except:
                    continue

        if not all_data:
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

            return summary

        except Exception as e:
            print(f"Error aggregating PV d'AG summaries: {e}")
            return None

    async def aggregate_diagnostic_summaries(
        self,
        property_id: int,
        db: Session
    ) -> Optional[DocumentSummary]:
        """
        Aggregate all diagnostic documents into one summary.
        Highlights urgent issues and compliance problems.
        """
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
                    data = json.loads(doc.extracted_data)
                    all_data.append({
                        "subcategory": doc.document_subcategory,
                        "filename": doc.filename,
                        "data": data
                    })
                except:
                    continue

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

            return summary

        except Exception as e:
            print(f"Error aggregating diagnostic summaries: {e}")
            return None
