"""Properties API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.property import Property
from app.schemas.property import (
    PropertyCreate,
    PropertyUpdate,
    PropertyResponse,
    PriceAnalysisResponse,
    DVFRecordResponse
)
from app.services.dvf_service import dvf_service

router = APIRouter()


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    property_data: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Create a new property for analysis."""
    property = Property(**property_data.dict(), user_id=int(current_user))

    # Calculate initial price per sqm if data available
    if property.asking_price and property.surface_area:
        property.price_per_sqm = property.asking_price / property.surface_area

    db.add(property)
    db.commit()
    db.refresh(property)
    return property


@router.get("/", response_model=List[PropertyResponse])
async def list_properties(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """List all properties for the current user."""
    properties = db.query(Property).filter(
        Property.user_id == int(current_user)
    ).offset(skip).limit(limit).all()
    return properties


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get a specific property by ID."""
    property = db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == int(current_user)
    ).first()

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    return property


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    property_update: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Update a property."""
    property = db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == int(current_user)
    ).first()

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    # Update fields
    for field, value in property_update.dict(exclude_unset=True).items():
        setattr(property, field, value)

    # Recalculate price per sqm if needed
    if property.asking_price and property.surface_area:
        property.price_per_sqm = property.asking_price / property.surface_area

    db.commit()
    db.refresh(property)
    return property


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Delete a property."""
    property = db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == int(current_user)
    ).first()

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    db.delete(property)
    db.commit()
    return None


@router.post("/{property_id}/analyze-price", response_model=PriceAnalysisResponse)
async def analyze_property_price(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Analyze property price against DVF comparable sales data.
    """
    property = db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == int(current_user)
    ).first()

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    if not property.asking_price or not property.surface_area:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property must have asking_price and surface_area for analysis"
        )

    # Get comparable sales
    comparable_sales = dvf_service.get_comparable_sales(
        db=db,
        postal_code=property.postal_code or "",
        property_type=property.property_type or "Appartement",
        surface_area=property.surface_area,
    )

    # Calculate price analysis
    analysis = dvf_service.calculate_price_analysis(
        asking_price=property.asking_price,
        surface_area=property.surface_area,
        comparable_sales=comparable_sales
    )

    # Update property with analysis results
    property.estimated_value = analysis["estimated_value"]
    property.market_comparison_score = analysis["confidence_score"]
    property.recommendation = analysis["recommendation"]

    db.commit()

    # Convert comparable sales to response format
    comparable_sales_response = [
        DVFRecordResponse.from_orm(sale) for sale in comparable_sales[:10]
    ]

    return PriceAnalysisResponse(
        **analysis,
        comparable_sales=comparable_sales_response
    )
