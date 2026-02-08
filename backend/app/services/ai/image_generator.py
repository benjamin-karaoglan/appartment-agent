"""
Image Generator - AI-powered photo redesign using Gemini.

Generates redesigned apartment photos using Google's Gemini image generation
capabilities with support for multi-turn editing conversations.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.core.config import settings
from app.prompts import get_prompt

logger = logging.getLogger(__name__)


class ImageGenerator:
    """
    AI service for apartment photo redesign using Gemini.

    Capabilities:
    - Image-to-image generation with text prompts
    - Multi-turn editing conversations
    - Multiple design style presets
    """

    def __init__(self):
        """Initialize Gemini client for image generation."""
        self.use_vertexai = settings.GEMINI_USE_VERTEXAI
        self.model = settings.GEMINI_IMAGE_MODEL  # Image generation model
        self.project = settings.GOOGLE_CLOUD_PROJECT
        self.location = settings.GOOGLE_CLOUD_LOCATION

        if self.use_vertexai:
            if not self.project or not self.location:
                raise RuntimeError("GOOGLE_CLOUD_PROJECT and LOCATION required for Vertex AI")
            self.client = genai.Client(vertexai=True, project=self.project, location=self.location)
        else:
            api_key = settings.GOOGLE_CLOUD_API_KEY
            if not api_key:
                raise RuntimeError("GOOGLE_CLOUD_API_KEY required for Gemini API")
            self.client = genai.Client(api_key=api_key)

        logger.info(f"ImageGenerator initialized with model: {self.model}")

    def _extract_image_part(self, response) -> Optional[types.Part]:
        """Extract first image output from response."""
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return None

        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []

        for p in parts:
            inline = getattr(p, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return types.Part.from_bytes(data=inline.data, mime_type=inline.mime_type)
        return None

    def _extract_text(self, response) -> str:
        """Extract text from response."""
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []
        return "\n".join(p.text for p in parts if getattr(p, "text", None)).strip()

    async def redesign_apartment(
        self,
        image_data: bytes,
        prompt: str,
        aspect_ratio: str = "16:9",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        reference_images: Optional[List[bytes]] = None,
    ) -> Dict[str, Any]:
        """
        Redesign an apartment photo.

        Args:
            image_data: Original photo bytes
            prompt: Redesign description
            aspect_ratio: Output aspect ratio
            conversation_history: Previous turns for multi-turn editing

        Returns:
            Dict with generated image data and metadata
        """
        start_time = time.time()

        try:
            image_part = types.Part.from_bytes(data=image_data, mime_type="image/png")
            contents = []

            # Add conversation history for multi-turn
            if conversation_history:
                for turn in conversation_history:
                    parts = []
                    if turn.get("role") == "user" and turn.get("content"):
                        parts.append(types.Part.from_text(text=turn["content"]))
                    elif turn.get("role") == "model" and turn.get("image"):
                        img_bytes = bytes.fromhex(turn["image"])
                        parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
                    if parts:
                        contents.append(types.Content(role=turn["role"], parts=parts))

            # Add current request
            user_parts = [image_part]
            if reference_images:
                for ref_data in reference_images:
                    user_parts.append(types.Part.from_bytes(data=ref_data, mime_type="image/png"))
            user_parts.append(types.Part.from_text(text=prompt))
            contents.append(types.Content(role="user", parts=user_parts))

            config = types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                temperature=0.4,
                top_p=0.95,
                max_output_tokens=2048,
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio, image_size="2K"),
            )

            logger.info(f"Generating redesign: {prompt[:100]}...")

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )

            text_response = self._extract_text(response)
            image_result = self._extract_image_part(response)

            if image_result is None:
                raise RuntimeError(f"No image returned. Response: {text_response}")

            image_bytes = getattr(image_result.inline_data, "data", None)
            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(f"Generated redesign ({len(image_bytes)} bytes) in {latency_ms}ms")

            return {
                "success": True,
                "image_data": image_bytes,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "model": self.model,
                "text_response": text_response,
            }

        except Exception as e:
            logger.error(f"Error generating redesign: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def create_detailed_prompt(
        self,
        base_style: str,
        room_type: str = "living room",
        additional_details: Optional[str] = None,
    ) -> str:
        """
        Create a detailed prompt for apartment redesign.

        Args:
            base_style: Design style preset
            room_type: Type of room
            additional_details: User-specified details

        Returns:
            Detailed narrative prompt
        """
        template_map = {
            "modern_norwegian": "redesign_modern_norwegian",
            "minimalist_scandinavian": "redesign_minimalist_scandinavian",
            "cozy_hygge": "redesign_cozy_hygge",
            "fancy_dark_modern": "redesign_fancy_dark_modern",
        }
        template_name = template_map.get(base_style, "redesign_modern_norwegian")
        prompt = get_prompt(template_name, room_type=room_type)
        if additional_details:
            prompt += f"\n\nAdditional requirements: {additional_details}"
        return prompt.strip()


# Singleton
_instance: Optional[ImageGenerator] = None


def get_image_generator() -> ImageGenerator:
    """Get or create the ImageGenerator singleton."""
    global _instance
    if _instance is None:
        _instance = ImageGenerator()
    return _instance


# Backward compatibility aliases
GeminiImageService = ImageGenerator
get_gemini_service = get_image_generator
