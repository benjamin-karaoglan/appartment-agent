"""Document schemas for request/response validation."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class DocumentUpload(BaseModel):
    """Schema for document upload."""
    property_id: Optional[int] = None
    document_category: str  # PV_AG, diagnostic, tax, charges, photo


class DocumentResponse(BaseModel):
    """Schema for document response."""
    id: int
    user_id: int
    property_id: Optional[int] = None
    filename: str
    file_type: str
    document_category: str
    document_subcategory: Optional[str] = None
    document_date: Optional[datetime] = None
    is_analyzed: bool
    analysis_summary: Optional[str] = None
    key_insights: Optional[List[str]] = None
    estimated_annual_cost: Optional[float] = None
    one_time_costs: Optional[List[Dict[str, Any]]] = None
    upload_date: datetime
    parsed_at: Optional[datetime] = None
    file_size: int

    class Config:
        from_attributes = True


class PVAGAnalysisResponse(BaseModel):
    """Schema for PV d'AG analysis response."""
    document_id: int
    summary: str
    upcoming_works: List[Dict[str, Any]]
    estimated_costs: Dict[str, float]
    risk_level: str  # low, medium, high
    key_findings: List[str]
    recommendations: List[str]


class DiagnosticAnalysisResponse(BaseModel):
    """Schema for diagnostic document analysis."""
    document_id: int
    dpe_rating: Optional[str] = None
    ges_rating: Optional[str] = None
    energy_consumption: Optional[float] = None
    has_amiante: bool = False
    has_plomb: bool = False
    risk_flags: List[str]
    estimated_renovation_cost: Optional[float] = None
    summary: str
    recommendations: List[str]


class TaxChargesAnalysisResponse(BaseModel):
    """Schema for tax and charges analysis."""
    document_id: int
    document_type: str  # taxe_fonciere, charges
    period_covered: str
    total_amount: float
    annual_amount: float
    breakdown: Dict[str, float]
    summary: str


class DocumentSummaryResponse(BaseModel):
    """Schema for aggregated document summary response."""
    id: int
    property_id: int
    category: str
    summary: Optional[str] = None
    key_findings: Optional[List[str]] = None
    total_estimated_annual_cost: Optional[float] = None
    total_one_time_costs: Optional[float] = None
    cost_breakdown: Optional[Dict[str, float]] = None
    copropriete_insights: Optional[Dict[str, Any]] = None
    diagnostic_issues: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    document_count: int

    class Config:
        from_attributes = True
