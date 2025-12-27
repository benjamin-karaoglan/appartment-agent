"""
Claude AI service for document analysis and insights with comprehensive logging.
"""

import anthropic
import logging
from typing import Dict, Any, List
import json
from app.core.config import settings

logger = logging.getLogger(__name__)


class ClaudeService:
    """Service for interacting with Claude AI API."""

    def __init__(self):
        logger.info("Initializing ClaudeService")
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.ANTHROPIC_MODEL
        logger.info(f"Using Claude model: {self.model}")

    async def analyze_pvag_document(self, document_text: str) -> Dict[str, Any]:
        """
        Analyze PV d'AG (Assembly General Meeting Minutes) to identify:
        - Upcoming works and their costs
        - Copropriété issues
        - Financial health indicators
        """
        logger.info(f"Analyzing PV d'AG document, text length: {len(document_text)} characters")

        prompt = f"""
Analyze the following French copropriété assembly meeting minutes (PV d'AG).

Extract and identify:
1. All upcoming works mentioned (travaux à venir)
2. Estimated costs for each work item
3. Financial health of the copropriété (budget, reserves, debts)
4. Any disputes or issues mentioned
5. Risk level for the buyer (low, medium, high)
6. Key findings that would impact a purchase decision
7. Specific recommendations for the buyer

Document text:
{document_text}

Provide your analysis in JSON format with the following structure:
{{
    "summary": "Brief overall summary",
    "upcoming_works": [
        {{"description": "work description", "estimated_cost": 0, "timeline": "when"}},
    ],
    "financial_health": {{
        "budget_status": "description",
        "reserves": 0,
        "outstanding_debts": 0,
        "health_score": 0-100
    }},
    "risk_level": "low|medium|high",
    "key_findings": ["finding 1", "finding 2"],
    "recommendations": ["recommendation 1", "recommendation 2"]
}}
"""

        try:
            logger.debug("Sending request to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            logger.debug(f"Received response from Claude, length: {len(response_text)} characters")

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text

            result = json.loads(json_str)
            logger.info("Successfully analyzed PV d'AG document")
            return result

        except Exception as e:
            logger.error(f"Error analyzing PV d'AG document: {e}", exc_info=True)
            raise

    async def analyze_diagnostic_document(self, document_text: str) -> Dict[str, Any]:
        """
        Analyze diagnostic documents (DPE, amiante, plomb) to identify:
        - Energy performance rating
        - Presence of hazardous materials
        - Renovation needs and estimated costs
        """
        logger.info(f"Analyzing diagnostic document, text length: {len(document_text)} characters")

        prompt = f"""
Analyze the following French property diagnostic document.

Extract and identify:
1. DPE (Energy Performance) rating (A-G)
2. GES (Greenhouse Gas) rating (A-G)
3. Energy consumption (kWh/m²/year)
4. Presence of amiante (asbestos)
5. Presence of plomb (lead)
6. Other risk factors or issues
7. Estimated renovation costs to improve rating
8. Specific recommendations for the buyer

Document text:
{document_text}

Provide your analysis in JSON format with the following structure:
{{
    "dpe_rating": "A-G or null",
    "ges_rating": "A-G or null",
    "energy_consumption": 0,
    "has_amiante": true/false,
    "has_plomb": true/false,
    "risk_flags": ["flag1", "flag2"],
    "estimated_renovation_cost": 0,
    "summary": "Brief summary",
    "recommendations": ["recommendation 1", "recommendation 2"]
}}
"""

        try:
            logger.debug("Sending diagnostic request to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            logger.debug(f"Received diagnostic response, length: {len(response_text)} characters")

            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text

            result = json.loads(json_str)
            logger.info("Successfully analyzed diagnostic document")
            return result

        except Exception as e:
            logger.error(f"Error analyzing diagnostic document: {e}", exc_info=True)
            raise

    async def analyze_tax_charges_document(self, document_text: str, document_type: str) -> Dict[str, Any]:
        """
        Analyze tax (Taxe Foncière) or charges documents.
        Extract costs and calculate annual amounts.
        """
        logger.info(f"Analyzing {document_type} document, text length: {len(document_text)} characters")

        prompt = f"""
Analyze the following French property {document_type} document.

Extract:
1. Total amount charged
2. Period covered (e.g., "3 months", "annual", "quarterly")
3. Breakdown of charges by category
4. Calculate the annual amount (if period is less than 1 year, multiply accordingly)

Document text:
{document_text}

Provide your analysis in JSON format:
{{
    "period_covered": "description of period",
    "total_amount": 0,
    "annual_amount": 0,
    "breakdown": {{
        "category1": 0,
        "category2": 0
    }},
    "summary": "Brief summary"
}}
"""

        try:
            logger.debug(f"Sending {document_type} request to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            logger.debug(f"Received {document_type} response, length: {len(response_text)} characters")

            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text

            result = json.loads(json_str)
            result["document_type"] = document_type
            logger.info(f"Successfully analyzed {document_type} document")
            return result

        except Exception as e:
            logger.error(f"Error analyzing {document_type} document: {e}", exc_info=True)
            raise

    async def analyze_property_photos(self, image_data: bytes, transformation_request: str) -> Dict[str, Any]:
        """
        Analyze property photos and provide style transformation suggestions.
        """
        import base64

        logger.info(f"Analyzing property photo, size: {len(image_data)} bytes, request: {transformation_request}")

        # Convert image to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        prompt = f"""
Analyze this apartment photo and provide:
1. Current style description
2. Condition assessment
3. Suggested improvements based on this request: {transformation_request}
4. Estimated renovation cost for suggested changes
5. Style transformation description

Provide detailed, actionable recommendations.
"""

        try:
            logger.debug("Sending photo analysis request to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
            )

            response_text = message.content[0].text
            logger.info("Successfully analyzed property photo")
            return {
                "analysis": response_text,
                "transformation_request": transformation_request
            }

        except Exception as e:
            logger.error(f"Error analyzing property photo: {e}", exc_info=True)
            raise

    async def generate_property_report(
        self,
        property_data: Dict[str, Any],
        price_analysis: Dict[str, Any],
        documents_analysis: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a comprehensive property analysis report.
        """
        logger.info("Generating comprehensive property report")

        prompt = f"""
Generate a comprehensive property purchase decision report for a French apartment.

Property Information:
{json.dumps(property_data, indent=2)}

Price Analysis:
{json.dumps(price_analysis, indent=2)}

Documents Analysis:
{json.dumps(documents_analysis, indent=2)}

Create a detailed report with:
1. Executive Summary (recommend buy/don't buy/further investigation)
2. Property Overview
3. Price Analysis and Market Comparison
4. Investment Score (0-100)
5. Risk Assessment
6. Financial Breakdown (total costs, annual costs)
7. Key Strengths
8. Key Concerns
9. Recommendations

Make the report clear, actionable, and data-driven.
"""

        try:
            logger.debug("Sending property report generation request to Claude API")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            report = message.content[0].text
            logger.info(f"Successfully generated property report, length: {len(report)} characters")
            return report

        except Exception as e:
            logger.error(f"Error generating property report: {e}", exc_info=True)
            raise


# Singleton instance
claude_service = ClaudeService()
