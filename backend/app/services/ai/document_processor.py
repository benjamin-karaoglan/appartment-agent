"""
Document Processor - Sequential document classification and analysis.

Processes documents individually using Gemini for classification
and type-specific analysis. Handles PV AG, diagnostics, taxes, and charges.
"""

import asyncio
import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.core.config import settings
from app.prompts import get_prompt

logger = logging.getLogger(__name__)


def _repair_json(json_str: str) -> str:
    """Attempt to repair truncated or malformed JSON from LLM responses."""
    # Count brackets to find imbalance
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")

    # Check for unterminated string (odd number of unescaped quotes)
    in_string = False
    i = 0
    while i < len(json_str):
        if json_str[i] == '"' and (i == 0 or json_str[i - 1] != "\\"):
            in_string = not in_string
        i += 1

    # If we're inside a string, close it
    if in_string:
        json_str += '"'

    # Close any trailing comma before adding brackets
    json_str = re.sub(r",\s*$", "", json_str)

    # Close open brackets/braces
    json_str += "]" * open_brackets + "}" * open_braces

    return json_str


def _extract_json(response_text: str) -> str:
    """Extract and clean JSON from LLM response."""
    # Find JSON start
    json_start = min(
        response_text.find("{") if response_text.find("{") != -1 else len(response_text),
        response_text.find("[") if response_text.find("[") != -1 else len(response_text),
    )
    if json_start > 0:
        response_text = response_text[json_start:]

    # Remove markdown blocks
    if "```" in response_text:
        response_text = re.sub(r"```(?:json)?\s*", "", response_text)

    # Fix number formatting
    response_text = re.sub(r":\s*(\d+),(\d+\.?\d*)", r": \1\2", response_text)
    response_text = re.sub(r":\s*(\d+),(\d+),(\d+\.?\d*)", r": \1\2\3", response_text)

    # Remove trailing commas
    response_text = re.sub(r",(\s*[}\]])", r"\1", response_text)

    # Attempt to repair truncated JSON
    response_text = _repair_json(response_text.strip())

    return response_text


class DocumentProcessor:
    """
    Sequential document processor using Gemini.

    Flow:
    1. Classify document type
    2. Apply type-specific analysis
    3. Return structured results
    """

    def __init__(self):
        """Initialize Gemini client."""
        logger.info("Initializing DocumentProcessor")

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

    def _get_config(
        self, max_tokens: int = 2000, temperature: float = 0.1
    ) -> types.GenerateContentConfig:
        """Get generation config."""
        return types.GenerateContentConfig(
            temperature=temperature, top_p=0.95, max_output_tokens=max_tokens
        )

    def _build_image_parts(self, images: List[str]) -> List[types.Part]:
        """Convert base64 images to Gemini parts."""
        parts = []
        for img_b64 in images:
            img_bytes = base64.b64decode(img_b64)
            parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        return parts

    async def classify_document(self, document: Dict[str, Any]) -> str:
        """Classify document type from first few pages."""
        filename = document.get("filename", "")
        images = document.get("file_data_base64", [])

        if not images:
            logger.warning(f"No images for: {filename}")
            return "other"

        parts = self._build_image_parts(images[:3])
        parts.append(
            types.Part.from_text(text=get_prompt("dp_classify_document", filename=filename))
        )

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[types.Content(role="user", parts=parts)],
                config=self._get_config(max_tokens=50),
            )
            category = self._extract_text(response).strip().lower()

            valid = {"pv_ag", "diagnostic", "diags", "taxe_fonciere", "charges", "other"}
            if category not in valid:
                logger.warning(f"Invalid category '{category}' for {filename}, mapping to 'other'")
                return "other"

            if category == "diagnostic":
                category = "diags"

            logger.info(f"Classified {filename} as: {category}")
            return category

        except Exception as e:
            logger.error(f"Classification error for {filename}: {e}")
            return "other"

    async def _process_with_prompt(self, document: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Generic processing with custom prompt."""
        filename = document.get("filename", "")
        images = document.get("file_data_base64", [])

        parts = self._build_image_parts(images)
        parts.append(types.Part.from_text(text=prompt))

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[types.Content(role="user", parts=parts)],
                config=self._get_config(),
            )
            response_text = _extract_json(self._extract_text(response))
            if not response_text:
                raise ValueError("Empty response")
            return json.loads(response_text)

        except Exception as e:
            logger.error(f"Processing error for {filename}: {e}")
            return {
                "summary": f"Error processing {filename}",
                "key_insights": [],
                "estimated_annual_cost": 0.0,
                "one_time_costs": 0.0,
            }

    async def process_pv_ag(
        self, document: Dict[str, Any], output_language: str = "French"
    ) -> Dict[str, Any]:
        """Process PV d'AG document."""
        prompt = get_prompt(
            "dp_process_pv_ag",
            filename=document.get("filename", ""),
            output_language=output_language,
        )
        return await self._process_with_prompt(document, prompt)

    async def process_diagnostic(
        self, document: Dict[str, Any], output_language: str = "French"
    ) -> Dict[str, Any]:
        """Process diagnostic document."""
        prompt = get_prompt(
            "dp_process_diagnostic",
            filename=document.get("filename", ""),
            output_language=output_language,
        )
        return await self._process_with_prompt(document, prompt)

    async def process_tax(
        self, document: Dict[str, Any], output_language: str = "French"
    ) -> Dict[str, Any]:
        """Process taxe foncière document."""
        prompt = get_prompt(
            "dp_process_tax", filename=document.get("filename", ""), output_language=output_language
        )
        return await self._process_with_prompt(document, prompt)

    async def process_charges(
        self, document: Dict[str, Any], output_language: str = "French"
    ) -> Dict[str, Any]:
        """Process charges document."""
        prompt = get_prompt(
            "dp_process_charges",
            filename=document.get("filename", ""),
            output_language=output_language,
        )
        return await self._process_with_prompt(document, prompt)

    async def process_other(
        self, document: Dict[str, Any], output_language: str = "French"
    ) -> Dict[str, Any]:
        """Process miscellaneous property document."""
        prompt = get_prompt(
            "dp_process_other",
            filename=document.get("filename", ""),
            output_language=output_language,
        )
        return await self._process_with_prompt(document, prompt)

    async def process_document(
        self, document: Dict[str, Any], output_language: str = "French"
    ) -> Dict[str, Any]:
        """Process a single document: classify and analyze."""
        filename = document.get("filename", "")
        document_id = document.get("document_id")

        logger.info(f"Processing: {filename} (ID: {document_id})")

        category = await self.classify_document(document)

        processors = {
            "pv_ag": self.process_pv_ag,
            "diags": self.process_diagnostic,
            "diagnostic": self.process_diagnostic,
            "taxe_fonciere": self.process_tax,
            "charges": self.process_charges,
            "other": self.process_other,
        }

        processor = processors.get(category, self.process_other)
        analysis = await processor(document, output_language=output_language)

        return {
            "filename": filename,
            "document_type": category,
            "result": analysis,
            "document_id": document_id,
        }

    async def synthesize_results(
        self, results: List[Dict[str, Any]], output_language: str = "French"
    ) -> Dict[str, Any]:
        """Synthesize all results into overall summary."""
        logger.info(f"Synthesizing {len(results)} documents")

        summaries = "\n".join(
            f"- {r.get('document_type', 'unknown')}: {r.get('result', {}).get('summary', 'No summary')}"
            for r in results
        )

        prompt = get_prompt(
            "dp_synthesize_results", summaries=summaries, output_language=output_language
        )

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
                config=self._get_config(max_tokens=1500),
            )
            return json.loads(_extract_json(self._extract_text(response)))

        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return {
                "summary": "Documents processed. Synthesis unavailable.",
                "total_annual_costs": 0.0,
                "total_one_time_costs": 0.0,
                "risk_level": "unknown",
                "key_findings": ["All documents processed"],
                "recommendations": ["Review individual documents"],
            }

    async def process_bulk_upload(
        self, documents: List[Dict[str, Any]], property_id: int, output_language: str = "French"
    ) -> Dict[str, Any]:
        """Process multiple documents sequentially."""
        logger.info(f"Bulk processing: {len(documents)} documents for property {property_id}")

        results = [
            await self.process_document(doc, output_language=output_language) for doc in documents
        ]
        synthesis = await self.synthesize_results(results, output_language=output_language)

        return {"processing_results": results, "synthesis": synthesis}


# Singleton
_instance: Optional[DocumentProcessor] = None


def get_document_processor() -> DocumentProcessor:
    """Get or create the DocumentProcessor singleton."""
    global _instance
    if _instance is None:
        _instance = DocumentProcessor()
    return _instance


# Backward compatibility
SimpleDocumentProcessor = DocumentProcessor
get_simple_processor = get_document_processor
