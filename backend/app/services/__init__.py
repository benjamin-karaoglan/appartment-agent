"""
Services package - Business logic and integrations.

Structure:
- app.services.ai - AI services (document analysis, image generation, processing)
- app.services.documents - Document parsing and bulk processing
- app.services.storage - Object storage (MinIO/GCS/S3)
- app.services.price_analysis - DVF price analysis
- app.services.dvf_service - DVF service (original implementation)
"""

# =============================================================================
# Primary Imports
# =============================================================================

# AI Services
from app.services.ai import (
    DocumentAnalyzer,
    DocumentProcessor,
    ImageGenerator,
    get_document_analyzer,
    get_document_processor,
    get_image_generator,
)

# Document Services
from app.services.documents import (
    BulkProcessor,
    DocumentParser,
    get_bulk_processor,
    get_document_parser,
)

# DVF Service
from app.services.dvf_service import DVFService

# Price Analysis
from app.services.price_analysis import (
    PriceAnalyzer,
    get_price_analyzer,
)

# Storage Service
from app.services.storage import (
    StorageService,
    get_storage_service,
)

# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# Old AI service names
GeminiLLMService = DocumentAnalyzer
get_gemini_llm_service = get_document_analyzer
GeminiImageService = ImageGenerator
get_gemini_service = get_image_generator
SimpleDocumentProcessor = DocumentProcessor
get_simple_processor = get_document_processor

# Old document service names
DocumentParsingService = DocumentParser
AsyncDocumentProcessor = BulkProcessor
get_async_processor = get_bulk_processor

# Old DVF names
get_dvf_service = get_price_analyzer

# =============================================================================
# All exports
# =============================================================================

__all__ = [
    # Primary (new names)
    "DocumentAnalyzer",
    "get_document_analyzer",
    "ImageGenerator",
    "get_image_generator",
    "DocumentProcessor",
    "get_document_processor",
    "DocumentParser",
    "get_document_parser",
    "BulkProcessor",
    "get_bulk_processor",
    "StorageService",
    "get_storage_service",
    "PriceAnalyzer",
    "get_price_analyzer",
    "DVFService",
    # Backward compatibility
    "GeminiLLMService",
    "get_gemini_llm_service",
    "GeminiImageService",
    "get_gemini_service",
    "SimpleDocumentProcessor",
    "get_simple_processor",
    "DocumentParsingService",
    "AsyncDocumentProcessor",
    "get_async_processor",
    "get_dvf_service",
]
