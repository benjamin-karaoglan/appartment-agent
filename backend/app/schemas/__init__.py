"""Pydantic schemas for request/response validation."""

from app.schemas.property import (
    PropertyBase,
    PropertyCreate,
    PropertyUpdate,
    PropertyResponse,
    DVFRecordResponse,
    PriceAnalysisResponse,
)
from app.schemas.document import (
    DocumentUpload,
    DocumentResponse,
    PVAGAnalysisResponse,
    DiagnosticAnalysisResponse,
    TaxChargesAnalysisResponse,
)

__all__ = [
    "PropertyBase",
    "PropertyCreate",
    "PropertyUpdate",
    "PropertyResponse",
    "DVFRecordResponse",
    "PriceAnalysisResponse",
    "DocumentUpload",
    "DocumentResponse",
    "PVAGAnalysisResponse",
    "DiagnosticAnalysisResponse",
    "TaxChargesAnalysisResponse",
]
