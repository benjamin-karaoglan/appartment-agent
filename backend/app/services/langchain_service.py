"""
LangChain service for document analysis using Claude.
Replaces direct Anthropic API calls with LangChain ChatAnthropic.
"""

import logging
import base64
from typing import Optional, List, Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class LangChainService:
    """Service for LangChain-based document analysis."""

    def __init__(self):
        """Initialize LangChain ChatAnthropic client."""
        self.chat_model = ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=4096,
            temperature=0.0
        )
        logger.info(f"Initialized LangChain ChatAnthropic with model: {settings.ANTHROPIC_MODEL}")

    def analyze_document_with_vision(
        self,
        images_base64: List[str],
        prompt_template: str,
        document_type: str
    ) -> Dict[str, Any]:
        """
        Analyze document using multimodal vision with LangChain.

        Args:
            images_base64: List of base64-encoded images
            prompt_template: Prompt template string
            document_type: Type of document being analyzed

        Returns:
            Dict with analysis results and metadata
        """
        try:
            # Build content list with images
            content = []

            # Add images
            for idx, image_b64 in enumerate(images_base64):
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_b64
                    }
                })

            # Add text prompt after images
            content.append({
                "type": "text",
                "text": prompt_template
            })

            # Create message
            message = HumanMessage(content=content)

            # Invoke model
            logger.info(f"Invoking ChatAnthropic for {document_type} analysis ({len(images_base64)} pages)")
            response = self.chat_model.invoke([message])

            # Extract response
            response_text = response.content
            tokens_used = response.response_metadata.get("usage", {}).get("total_tokens", 0)

            # Estimate cost (approximate, based on Claude pricing)
            input_tokens = response.response_metadata.get("usage", {}).get("input_tokens", 0)
            output_tokens = response.response_metadata.get("usage", {}).get("output_tokens", 0)
            cost = self._estimate_cost(input_tokens, output_tokens)

            logger.info(f"Analysis complete: {tokens_used} tokens, ~${cost:.4f}")

            return {
                "response": response_text,
                "model": settings.ANTHROPIC_MODEL,
                "tokens_used": tokens_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost": cost,
                "document_type": document_type
            }

        except Exception as e:
            logger.error(f"Error analyzing document with LangChain: {e}")
            raise

    def analyze_text(
        self,
        text_content: str,
        prompt_template: str,
        document_type: str
    ) -> Dict[str, Any]:
        """
        Analyze text content using LangChain.

        Args:
            text_content: Text to analyze
            prompt_template: Prompt template string
            document_type: Type of document being analyzed

        Returns:
            Dict with analysis results and metadata
        """
        try:
            # Create prompt
            full_prompt = f"{prompt_template}\n\nDocument content:\n{text_content}"

            # Create message
            message = HumanMessage(content=full_prompt)

            # Invoke model
            logger.info(f"Invoking ChatAnthropic for {document_type} text analysis")
            response = self.chat_model.invoke([message])

            # Extract response
            response_text = response.content
            tokens_used = response.response_metadata.get("usage", {}).get("total_tokens", 0)

            # Estimate cost
            input_tokens = response.response_metadata.get("usage", {}).get("input_tokens", 0)
            output_tokens = response.response_metadata.get("usage", {}).get("output_tokens", 0)
            cost = self._estimate_cost(input_tokens, output_tokens)

            logger.info(f"Text analysis complete: {tokens_used} tokens, ~${cost:.4f}")

            return {
                "response": response_text,
                "model": settings.ANTHROPIC_MODEL,
                "tokens_used": tokens_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost": cost,
                "document_type": document_type
            }

        except Exception as e:
            logger.error(f"Error analyzing text with LangChain: {e}")
            raise

    def aggregate_documents(
        self,
        summaries: List[str],
        prompt_template: str,
        category: str
    ) -> Dict[str, Any]:
        """
        Aggregate multiple document summaries using LangChain.

        Args:
            summaries: List of document summaries to aggregate
            prompt_template: Prompt template for aggregation
            category: Category of documents being aggregated

        Returns:
            Dict with aggregated analysis and metadata
        """
        try:
            # Build content with all summaries
            combined_content = f"{prompt_template}\n\n"
            for idx, summary in enumerate(summaries, 1):
                combined_content += f"Document {idx}:\n{summary}\n\n"

            # Create message
            message = HumanMessage(content=combined_content)

            # Invoke model
            logger.info(f"Invoking ChatAnthropic for {category} aggregation ({len(summaries)} documents)")
            response = self.chat_model.invoke([message])

            # Extract response
            response_text = response.content
            tokens_used = response.response_metadata.get("usage", {}).get("total_tokens", 0)

            # Estimate cost
            input_tokens = response.response_metadata.get("usage", {}).get("input_tokens", 0)
            output_tokens = response.response_metadata.get("usage", {}).get("output_tokens", 0)
            cost = self._estimate_cost(input_tokens, output_tokens)

            logger.info(f"Aggregation complete: {tokens_used} tokens, ~${cost:.4f}")

            return {
                "response": response_text,
                "model": settings.ANTHROPIC_MODEL,
                "tokens_used": tokens_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost": cost,
                "category": category,
                "num_documents": len(summaries)
            }

        except Exception as e:
            logger.error(f"Error aggregating documents with LangChain: {e}")
            raise

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost based on token usage.

        Pricing (as of 2024, approximate):
        - Claude 3 Haiku: $0.25/1M input, $1.25/1M output
        - Claude 3 Sonnet: $3/1M input, $15/1M output
        - Claude 3.5 Sonnet: $3/1M input, $15/1M output
        """
        # Use Haiku pricing as default (most common for this use case)
        input_cost_per_1m = 0.25
        output_cost_per_1m = 1.25

        # Check if using Sonnet
        if "sonnet" in settings.ANTHROPIC_MODEL.lower():
            input_cost_per_1m = 3.0
            output_cost_per_1m = 15.0

        input_cost = (input_tokens / 1_000_000) * input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * output_cost_per_1m

        return input_cost + output_cost


# Singleton instance
_langchain_service: Optional[LangChainService] = None


def get_langchain_service() -> LangChainService:
    """Get or create LangChain service singleton."""
    global _langchain_service
    if _langchain_service is None:
        _langchain_service = LangChainService()
    return _langchain_service
