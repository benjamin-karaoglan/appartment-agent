"""Property schemas for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PropertyBase(BaseModel):
    """Base property schema."""
    address: str
    postal_code: Optional[str] = None
    city: Optional[str] = None
    department: Optional[str] = None
    asking_price: Optional[float] = None
    surface_area: Optional[float] = None
    rooms: Optional[int] = None
    property_type: Optional[str] = None
    floor: Optional[int] = None
    building_year: Optional[int] = None


class PropertyCreate(PropertyBase):
    """Schema for creating a new property."""
    pass


class PropertyUpdate(BaseModel):
    """Schema for updating a property."""
    address: Optional[str] = None
    asking_price: Optional[float] = None
    surface_area: Optional[float] = None
    rooms: Optional[int] = None
    property_type: Optional[str] = None
    floor: Optional[int] = None
    building_year: Optional[int] = None


class PropertyResponse(PropertyBase):
    """Schema for property response."""
    id: int
    user_id: int
    estimated_value: Optional[float] = None
    price_per_sqm: Optional[float] = None
    market_comparison_score: Optional[float] = None
    recommendation: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DVFRecordResponse(BaseModel):
    """Schema for DVF record response."""
    id: int
    sale_date: datetime
    sale_price: float
    address: str
    postal_code: str
    city: str
    property_type: str
    surface_area: Optional[float] = None
    rooms: Optional[int] = None
    price_per_sqm: Optional[float] = None

    class Config:
        from_attributes = True


class PriceAnalysisResponse(BaseModel):
    """Schema for price analysis response."""
    estimated_value: float
    price_per_sqm: float
    market_avg_price_per_sqm: float
    price_deviation_percent: float
    comparable_sales: list[DVFRecordResponse]
    recommendation: str
    confidence_score: float
