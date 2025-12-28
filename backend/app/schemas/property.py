"""Property schemas for request/response validation."""

from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, Union, List
from datetime import datetime, date
import json


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


class LotDetail(BaseModel):
    """Schema for individual lot in a multi-unit transaction."""
    id: int
    surface_area: Optional[float] = None
    rooms: Optional[int] = None
    price_per_sqm: Optional[float] = None
    land_surface: Optional[float] = None


class DVFRecordResponse(BaseModel):
    """Schema for DVF record response."""
    id: int
    sale_date: Union[datetime, date]
    sale_price: float
    address: str
    postal_code: str
    city: str
    property_type: str
    surface_area: Optional[float] = None
    rooms: Optional[int] = None
    price_per_sqm: Optional[float] = None
    is_outlier: Optional[bool] = False  # Flag for IQR outlier detection

    # Multi-unit sale fields
    unit_count: Optional[int] = 1  # Number of lots (1 = single, >1 = multi-unit)
    is_multi_unit: Optional[bool] = False
    lots_detail: Optional[List[LotDetail]] = None

    @field_validator('sale_date', mode='before')
    @classmethod
    def convert_date_to_datetime(cls, v):
        """Convert date to datetime for consistent API response."""
        if isinstance(v, date) and not isinstance(v, datetime):
            return datetime.combine(v, datetime.min.time())
        return v

    class Config:
        from_attributes = True


class DVFGroupedTransactionResponse(BaseModel):
    """Schema for grouped DVF transaction response (multi-unit sales aggregated)."""
    id: int
    transaction_group_id: str
    sale_date: Union[datetime, date]
    sale_price: float
    address: str
    postal_code: str
    city: str
    property_type: str
    total_surface_area: Optional[float] = None  # SUM of all lots
    total_rooms: Optional[int] = None  # SUM of all lots
    grouped_price_per_sqm: Optional[float] = None  # Correct grouped price/m²
    unit_count: int  # Number of lots in transaction
    is_multi_unit: Optional[bool] = None  # Calculated from unit_count
    lots_detail: Optional[List[LotDetail]] = None  # Individual lots for drill-down
    is_outlier: Optional[bool] = False

    @field_validator('sale_date', mode='before')
    @classmethod
    def convert_date_to_datetime(cls, v):
        """Convert date to datetime for consistent API response."""
        if isinstance(v, date) and not isinstance(v, datetime):
            return datetime.combine(v, datetime.min.time())
        return v

    @field_validator('lots_detail', mode='before')
    @classmethod
    def parse_lots_detail(cls, v):
        """Parse JSON string to list of dicts."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @model_validator(mode='after')
    def calculate_is_multi_unit(self):
        """Determine if multi-unit based on unit_count."""
        if self.is_multi_unit is None:
            self.is_multi_unit = self.unit_count > 1
        return self

    class Config:
        from_attributes = True


class PriceAnalysisResponse(BaseModel):
    """Schema for price analysis response."""
    estimated_value: float
    price_per_sqm: float
    market_avg_price_per_sqm: float
    market_median_price_per_sqm: Optional[float] = None
    price_deviation_percent: float
    comparable_sales: list[
        Union[DVFRecordResponse, DVFGroupedTransactionResponse]
    ]
    recommendation: str
    confidence_score: float
    comparables_count: Optional[int] = None
    market_trend_annual: Optional[float] = None
    analysis_type: Optional[str] = None
    trend_projection: Optional[dict] = None
