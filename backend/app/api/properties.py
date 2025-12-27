"""Properties API routes."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.property import Property, DVFRecord
from app.schemas.property import (
    PropertyCreate,
    PropertyUpdate,
    PropertyResponse,
    PriceAnalysisResponse,
    DVFRecordResponse
)
from app.services.dvf_service import dvf_service

router = APIRouter()


class AddressSearchResult(BaseModel):
    """Address search result."""
    address: str
    postal_code: str
    city: str
    property_type: str
    count: int  # Number of sales at this address


@router.get("/search-addresses", response_model=List[AddressSearchResult])
async def search_addresses(
    q: str = Query(..., min_length=2, description="Search query (at least 2 characters)"),
    postal_code: str = Query(None, description="Filter by postal code"),
    limit: int = Query(20, le=100, description="Maximum results to return"),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Search for addresses in DVF database.
    Returns unique addresses with sale history.
    Searches for street names (voie) - user can type partial street name.
    """
    # Normalize search query to uppercase (DVF data is in uppercase)
    search_query = q.upper().strip()

    # Build query - search in address field
    # User might type: "56 notre" or just "notre dame" or "56"
    query = db.query(
        DVFRecord.address,
        DVFRecord.postal_code,
        DVFRecord.city,
        DVFRecord.property_type,
        func.count(DVFRecord.id).label('count')
    ).filter(
        DVFRecord.address.isnot(None),
        DVFRecord.address != ''
    )

    # Search strategy: match anywhere in address for better results
    # This handles cases like "18 rue jean mermoz" or just "jean mermoz"
    query = query.filter(DVFRecord.address.ilike(f'%{search_query}%'))

    # Filter by postal code if provided
    if postal_code:
        query = query.filter(DVFRecord.postal_code == postal_code)

    # Group by unique address + postal code + city ONLY
    # Aggregate property types to show all types at this address
    from sqlalchemy import func as sqlfunc
    query = db.query(
        DVFRecord.address,
        DVFRecord.postal_code,
        DVFRecord.city,
        sqlfunc.string_agg(sqlfunc.distinct(DVFRecord.property_type), ', ').label('property_types'),
        func.count(DVFRecord.id).label('count')
    ).filter(
        DVFRecord.address.isnot(None),
        DVFRecord.address != '',
        DVFRecord.address.ilike(f'%{search_query}%')
    )

    # Filter by postal code if provided
    if postal_code:
        query = query.filter(DVFRecord.postal_code == postal_code)

    query = query.group_by(
        DVFRecord.address,
        DVFRecord.postal_code,
        DVFRecord.city
    ).order_by(
        func.count(DVFRecord.id).desc()  # Most sales first
    ).limit(limit)

    results = query.all()

    return [
        AddressSearchResult(
            address=r.address,
            postal_code=r.postal_code,
            city=r.city,
            property_type=r.property_types or 'Appartement',  # Default to Appartement
            count=r.count
        )
        for r in results
    ]


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
    analysis_type: str = Query("simple", description="Analysis type: 'simple' or 'trend'"),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Analyze property price against DVF comparable sales data.

    Analysis types:
    - 'simple': Use exact address sales (or neighbors if none found)
    - 'trend': Project 2025 value using neighboring address trends
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

    if analysis_type == "trend":
        # TREND ANALYSIS: Get exact address sales + neighboring sales for trend
        exact_sales = dvf_service.get_comparable_sales(
            db=db,
            postal_code=property.postal_code or "",
            property_type=property.property_type or "Appartement",
            surface_area=property.surface_area,
            address=property.address or "",
        )

        neighboring_sales = dvf_service.get_neighboring_sales_for_trend(
            db=db,
            postal_code=property.postal_code or "",
            property_type=property.property_type or "Appartement",
            surface_area=property.surface_area,
            address=property.address or "",
        )

        # Check if we have enough data
        if not exact_sales and not neighboring_sales:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No comparable sales found for this property. "
                    "This may be due to: (1) The property address is not in the DVF database, "
                    "(2) The DVF data file is incomplete or outdated, "
                    "or (3) There are no recent sales in the area matching the property criteria. "
                    "Please note: DVF data may not include all sales and may lag behind official sources."
                )
            )

        # Detect outliers in neighboring sales
        neighboring_outlier_flags = dvf_service.detect_outliers_iqr(neighboring_sales)

        # Calculate trend-based projection (excluding outliers)
        neighboring_outlier_indices = [i for i, is_outlier in enumerate(neighboring_outlier_flags) if is_outlier]
        filtered_neighboring_sales = [sale for i, sale in enumerate(neighboring_sales) if i not in neighboring_outlier_indices]

        trend_projection = dvf_service.calculate_trend_based_projection(
            exact_address_sales=exact_sales,
            neighboring_sales=filtered_neighboring_sales,
            surface_area=property.surface_area
        )

        # Detect outliers in exact/comparable sales
        comparable_for_analysis = exact_sales if exact_sales else neighboring_sales
        outlier_flags = dvf_service.detect_outliers_iqr(comparable_for_analysis)
        outlier_indices = [i for i, is_outlier in enumerate(outlier_flags) if is_outlier]

        # Use regular analysis as base (excluding outliers)
        analysis = dvf_service.calculate_price_analysis(
            asking_price=property.asking_price,
            surface_area=property.surface_area,
            comparable_sales=comparable_for_analysis,
            exclude_indices=outlier_indices,
            apply_time_adjustment=False  # Use raw prices for base analysis
        )

        # Add trend projection data and data source info
        # Include neighboring sales list in the trend_projection for the UI
        trend_projection_with_sales = trend_projection.copy()
        trend_projection_with_sales["neighboring_sales"] = [
            {
                "address": sale.address,
                "sale_date": sale.sale_date.isoformat() if hasattr(sale.sale_date, 'isoformat') else str(sale.sale_date),
                "sale_price": sale.sale_price,
                "surface_area": sale.surface_area,
                "price_per_sqm": sale.price_per_sqm,
                "is_outlier": neighboring_outlier_flags[i] if i < len(neighboring_outlier_flags) else False
            }
            for i, sale in enumerate(neighboring_sales)
        ]

        analysis.update({
            "analysis_type": "trend",
            "trend_projection": trend_projection_with_sales,
            "data_source": "exact_address" if exact_sales else "neighboring_addresses",
            "exact_sales_count": len(exact_sales),
            "neighboring_sales_count": len(neighboring_sales)
        })

        # Add outlier flags to comparable sales response
        comparable_sales_response = []
        for i, sale in enumerate(comparable_for_analysis[:10]):
            sale_response = DVFRecordResponse.from_orm(sale)
            sale_response.is_outlier = outlier_flags[i] if i < len(outlier_flags) else False
            comparable_sales_response.append(sale_response)

    else:
        # SIMPLE ANALYSIS: Use ONLY exact address sales (no neighbors)
        comparable_sales = dvf_service.get_exact_address_sales(
            db=db,
            postal_code=property.postal_code or "",
            property_type=property.property_type or "Appartement",
            address=property.address or "",
        )

        if not comparable_sales:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No sales found at the exact address {property.address}. "
                    "This could mean: (1) No recent sales at this specific building number, "
                    "(2) The address is not in the DVF database, or (3) Sales data is incomplete. "
                    "Try using 'Trend Analysis' instead to see neighboring sales and projected values. "
                    f"You can also import more recent DVF data from https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/"
                )
            )

        # Detect outliers using IQR method
        outlier_flags = dvf_service.detect_outliers_iqr(comparable_sales)

        # Calculate price analysis (excluding outliers by default)
        outlier_indices = [i for i, is_outlier in enumerate(outlier_flags) if is_outlier]
        analysis = dvf_service.calculate_price_analysis(
            asking_price=property.asking_price,
            surface_area=property.surface_area,
            comparable_sales=comparable_sales,
            exclude_indices=outlier_indices,
            apply_time_adjustment=False  # Use raw prices for simple analysis
        )

        analysis["analysis_type"] = "simple"

        # Add outlier flags to response
        comparable_sales_response = []
        for i, sale in enumerate(comparable_sales[:10]):
            sale_response = DVFRecordResponse.from_orm(sale)
            sale_response.is_outlier = outlier_flags[i] if i < len(outlier_flags) else False
            comparable_sales_response.append(sale_response)

    # Update property with analysis results
    property.estimated_value = analysis["estimated_value"]
    property.market_comparison_score = analysis["confidence_score"]
    property.recommendation = analysis["recommendation"]

    db.commit()

    return PriceAnalysisResponse(
        **analysis,
        comparable_sales=comparable_sales_response
    )


@router.post("/{property_id}/recalculate-analysis")
async def recalculate_analysis(
    property_id: int,
    excluded_sale_ids: List[int],
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Recalculate price analysis excluding specific sales by their IDs.
    Used when user toggles outlier inclusion/exclusion checkboxes.
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

    # Get the latest analysis data from property (we need to know what sales were used)
    # For simplicity, we'll re-fetch the comparable sales
    # This assumes simple analysis for now
    comparable_sales = dvf_service.get_exact_address_sales(
        db=db,
        postal_code=property.postal_code or "",
        property_type=property.property_type or "Appartement",
        address=property.address or "",
    )

    if not comparable_sales:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No comparable sales found"
        )

    # Build exclusion indices based on sale IDs
    sale_id_set = set(excluded_sale_ids)
    exclude_indices = [i for i, sale in enumerate(comparable_sales) if sale.id in sale_id_set]

    # Recalculate analysis (use raw prices, no time adjustment for simple analysis)
    analysis = dvf_service.calculate_price_analysis(
        asking_price=property.asking_price,
        surface_area=property.surface_area,
        comparable_sales=comparable_sales,
        exclude_indices=exclude_indices,
        apply_time_adjustment=False
    )

    # Log the calculated values for debugging
    print(f"🔍 RECALCULATE ANALYSIS:")
    print(f"   Excluded indices: {exclude_indices}")
    print(f"   Total sales: {len(comparable_sales)}")
    print(f"   Filtered sales: {len(comparable_sales) - len(exclude_indices)}")
    print(f"   Estimated value: {analysis['estimated_value']:.2f} €")
    print(f"   Market avg: {analysis['market_avg_price_per_sqm']:.2f} €/m²")
    print(f"   Surface area: {property.surface_area} m²")

    # Return all analysis metrics
    return {
        "estimated_value": analysis["estimated_value"],
        "price_per_sqm": analysis["price_per_sqm"],
        "market_avg_price_per_sqm": analysis["market_avg_price_per_sqm"],
        "market_median_price_per_sqm": analysis.get("market_median_price_per_sqm"),
        "price_deviation_percent": analysis["price_deviation_percent"],
        "recommendation": analysis["recommendation"],
        "confidence_score": analysis["confidence_score"],
        "comparables_count": analysis.get("comparables_count"),
        "market_trend_annual": analysis.get("market_trend_annual"),
    }


@router.post("/{property_id}/recalculate-trend")
async def recalculate_trend(
    property_id: int,
    excluded_neighboring_sale_ids: List[int],
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Recalculate trend analysis excluding specific neighboring sales by their IDs.
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

    # Get exact address sales
    exact_sales = dvf_service.get_exact_address_sales(
        db=db,
        postal_code=property.postal_code or "",
        property_type=property.property_type or "Appartement",
        address=property.address or "",
    )

    # Get neighboring sales
    neighboring_sales = dvf_service.get_neighboring_sales_for_trend(
        db=db,
        postal_code=property.postal_code or "",
        property_type=property.property_type or "Appartement",
        surface_area=property.surface_area,
        address=property.address or "",
    )

    if not exact_sales and not neighboring_sales:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sales found for trend analysis"
        )

    # Filter out user-excluded sales
    excluded_id_set = set(excluded_neighboring_sale_ids)
    filtered_neighboring_sales = [
        sale for sale in neighboring_sales
        if sale.id not in excluded_id_set
    ]

    # Detect outliers in ALL neighboring sales (including user-excluded ones)
    neighboring_outlier_flags = dvf_service.detect_outliers_iqr(neighboring_sales)

    # Recalculate trend projection with filtered sales
    trend_projection = dvf_service.calculate_trend_based_projection(
        exact_address_sales=exact_sales,
        neighboring_sales=filtered_neighboring_sales,
        surface_area=property.surface_area
    )

    # Include full neighboring sales list with outlier flags for UI
    trend_projection_with_sales = trend_projection.copy()
    trend_projection_with_sales["neighboring_sales"] = [
        {
            "id": sale.id,
            "address": sale.address,
            "sale_date": sale.sale_date.isoformat() if hasattr(sale.sale_date, 'isoformat') else str(sale.sale_date),
            "sale_price": sale.sale_price,
            "surface_area": sale.surface_area,
            "price_per_sqm": sale.price_per_sqm,
            "is_outlier": neighboring_outlier_flags[i] if i < len(neighboring_outlier_flags) else False
        }
        for i, sale in enumerate(neighboring_sales)
    ]

    # Return updated trend projection with sales list
    return {
        "trend_projection": trend_projection_with_sales,
        "neighboring_sales_count": len(filtered_neighboring_sales),
    }
