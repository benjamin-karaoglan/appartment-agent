"""Properties API routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.better_auth_security import get_current_user_hybrid as get_current_user
from app.core.database import get_db
from app.core.i18n import get_local, translate
from app.models.property import DVFRecord, DVFStats, Property
from app.schemas.property import (
    DVFGroupedTransactionResponse,
    PriceAnalysisResponse,
    PropertyCreate,
    PropertyResponse,
    PropertyUpdate,
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


class DVFStatsResponse(BaseModel):
    """DVF statistics response."""

    total_records: int
    total_imports: int
    last_updated: str | None
    formatted_count: str  # Human-readable format like "1.36M"


@router.get("/dvf-stats", response_model=DVFStatsResponse)
async def get_dvf_stats(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get DVF database statistics.
    Returns total records count and last update time.
    Public endpoint - no authentication required for dashboard stats.
    """
    get_local(request)

    # Get stats from dvf_stats table
    stats = db.query(DVFStats).filter(DVFStats.id == 1).first()

    if stats:
        total = stats.total_records
        last_updated = stats.last_updated.isoformat() if stats.last_updated else None
        total_imports = stats.total_imports
    else:
        # Fallback: count directly from dvf_records (slower for large datasets)
        total = db.query(func.count(DVFRecord.id)).scalar() or 0
        last_updated = None
        total_imports = 0

    # Format the count for display
    if total >= 1_000_000:
        formatted = f"{total / 1_000_000:.2f}M"
    elif total >= 1_000:
        formatted = f"{total / 1_000:.1f}K"
    else:
        formatted = str(total)

    return DVFStatsResponse(
        total_records=total,
        total_imports=total_imports,
        last_updated=last_updated,
        formatted_count=formatted,
    )


@router.get("/search-addresses", response_model=List[AddressSearchResult])
async def search_addresses(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query (at least 2 characters)"),
    postal_code: str = Query(None, description="Filter by postal code"),
    limit: int = Query(20, le=100, description="Maximum results to return"),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Search for addresses in DVF database.
    Returns unique addresses with sale history.
    Searches for street names (voie) - user can type partial street name.
    """
    get_local(request)

    # Normalize search query to uppercase (DVF data is in uppercase)
    search_query = q.upper().strip()

    # Build query - search in address field
    # User might type: "56 notre" or just "notre dame" or "56"
    query = db.query(
        DVFRecord.address,
        DVFRecord.postal_code,
        DVFRecord.city,
        DVFRecord.property_type,
        func.count(DVFRecord.id).label("count"),
    ).filter(DVFRecord.address.isnot(None), DVFRecord.address != "")

    # Search strategy: match anywhere in address for better results
    # This handles cases like "18 rue jean mermoz" or just "jean mermoz"
    query = query.filter(DVFRecord.address.ilike(f"%{search_query}%"))

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
        sqlfunc.string_agg(sqlfunc.distinct(DVFRecord.property_type), ", ").label("property_types"),
        func.count(DVFRecord.id).label("count"),
    ).filter(
        DVFRecord.address.isnot(None),
        DVFRecord.address != "",
        DVFRecord.address.ilike(f"%{search_query}%"),
    )

    # Filter by postal code if provided
    if postal_code:
        query = query.filter(DVFRecord.postal_code == postal_code)

    query = (
        query.group_by(DVFRecord.address, DVFRecord.postal_code, DVFRecord.city)
        .order_by(
            func.count(DVFRecord.id).desc()  # Most sales first
        )
        .limit(limit)
    )

    results = query.all()

    return [
        AddressSearchResult(
            address=r.address,
            postal_code=r.postal_code,
            city=r.city,
            property_type=r.property_types or "Appartement",  # Default to Appartement
            count=r.count,
        )
        for r in results
    ]


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    request: Request,
    property_data: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Create a new property for analysis."""
    get_local(request)

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
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    """List all properties for the current user."""
    get_local(request)

    properties = (
        db.query(Property)
        .filter(Property.user_id == int(current_user))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return properties


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Get a specific property by ID."""
    locale = get_local(request)

    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    return property


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    request: Request,
    property_update: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Update a property."""
    locale = get_local(request)

    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Delete a property."""
    locale = get_local(request)

    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    db.delete(property)
    db.commit()
    return None


@router.post("/{property_id}/analyze-price", response_model=PriceAnalysisResponse)
async def analyze_property_price(
    property_id: int,
    request: Request,
    analysis_type: str = Query("simple", description="Analysis type: 'simple' or 'trend'"),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Analyze property price against DVF comparable sales data.

    Analysis types:
    - 'simple': Use exact address sales (or neighbors if none found)
    - 'trend': Project 2025 value using neighboring address trends
    """
    locale = get_local(request)

    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    if not property.asking_price or not property.surface_area:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("property_needs_price_surface", locale),
        )

    if analysis_type == "trend":
        # TREND ANALYSIS: Get GROUPED exact address sales + neighboring sales for trend
        grouped_exact_sales = dvf_service.get_grouped_exact_address_sales(
            db=db,
            postal_code=property.postal_code or "",
            property_type=property.property_type or "Appartement",
            address=property.address or "",
        )

        # Convert grouped sales to compatible format for analysis
        exact_sales = []
        for sale in grouped_exact_sales:

            class CompatibleSale:
                def __init__(self, grouped_sale):
                    self.id = grouped_sale.id
                    self.sale_date = grouped_sale.sale_date
                    self.sale_price = grouped_sale.sale_price
                    self.surface_area = grouped_sale.total_surface_area
                    self.price_per_sqm = grouped_sale.grouped_price_per_sqm
                    self.address = grouped_sale.address
                    self.city = grouped_sale.city
                    self.postal_code = grouped_sale.postal_code

            exact_sales.append(CompatibleSale(sale))

        # Get neighboring sales for trend (ONLY 2024-2025 data for projection)
        neighboring_sales = dvf_service.get_neighboring_sales_for_trend(
            db=db,
            postal_code=property.postal_code or "",
            property_type=property.property_type or "Appartement",
            surface_area=property.surface_area,
            address=property.address or "",
            months_back=24,  # Only current + past year (2024-2025)
        )

        # Check if we have enough data
        if not exact_sales and not neighboring_sales:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=translate("no_comparable_sales", locale),
            )

        # Detect outliers in neighboring sales
        neighboring_outlier_flags = dvf_service.detect_outliers_iqr(neighboring_sales)

        # CRITICAL: Filter out outliers for consistent trend calculation (same as chart)
        filtered_neighboring_sales = [
            sale for i, sale in enumerate(neighboring_sales) if not neighboring_outlier_flags[i]
        ]

        outliers_excluded = len(neighboring_sales) - len(filtered_neighboring_sales)

        print(f"\n🎯 INITIAL TREND ANALYSIS for property {property_id}")
        print(f"   Exact address sales: {len(exact_sales)}")
        print(f"   Total neighboring sales: {len(neighboring_sales)}")
        print(f"   Outliers excluded: {outliers_excluded}")
        print(f"   Filtered neighboring sales: {len(filtered_neighboring_sales)}")

        # Calculate trend-based projection with FILTERED sales (outliers removed)
        trend_projection = dvf_service.calculate_trend_based_projection(
            exact_address_sales=exact_sales,
            neighboring_sales=filtered_neighboring_sales,  # Use filtered sales WITHOUT outliers
            surface_area=property.surface_area,
        )

        print(f"   Initial trend_used: {trend_projection.get('trend_used', 'N/A')}%")
        print(f"   Initial sample size: {trend_projection.get('trend_sample_size', 'N/A')}")

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
            apply_time_adjustment=False,  # Use raw prices for base analysis
            locale=locale,
        )

        # Add trend projection data and data source info
        # Include neighboring sales list in the trend_projection for the UI
        trend_projection_with_sales = trend_projection.copy()
        trend_projection_with_sales["neighboring_sales"] = [
            {
                "id": sale.id,  # CRITICAL: Include ID for frontend toggling
                "address": sale.address,
                "sale_date": sale.sale_date.isoformat()
                if hasattr(sale.sale_date, "isoformat")
                else str(sale.sale_date),
                "sale_price": sale.sale_price,
                "surface_area": sale.surface_area,
                "price_per_sqm": sale.price_per_sqm,
                "is_outlier": neighboring_outlier_flags[i]
                if i < len(neighboring_outlier_flags)
                else False,
            }
            for i, sale in enumerate(neighboring_sales)
        ]

        analysis.update(
            {
                "analysis_type": "trend",
                "trend_projection": trend_projection_with_sales,
                "data_source": "exact_address" if exact_sales else "neighboring_addresses",
                "exact_sales_count": len(exact_sales),
                "neighboring_sales_count": len(
                    filtered_neighboring_sales
                ),  # Use filtered count (outliers excluded)
            }
        )

        # Add outlier flags to comparable sales response (using grouped format)
        comparable_sales_response = []
        for i, sale in enumerate(grouped_exact_sales[:10]):
            sale_response = DVFGroupedTransactionResponse.from_orm(sale)
            sale_response.is_outlier = outlier_flags[i] if i < len(outlier_flags) else False
            sale_response.is_multi_unit = sale.unit_count > 1
            comparable_sales_response.append(sale_response)

    else:
        # SIMPLE ANALYSIS: Use GROUPED exact address sales (multi-unit aggregated)
        grouped_sales = dvf_service.get_grouped_exact_address_sales(
            db=db,
            postal_code=property.postal_code or "",
            property_type=property.property_type or "Appartement",
            address=property.address or "",
        )

        if not grouped_sales:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=translate("no_exact_address_sales", locale, address=property.address),
            )

        # Convert grouped sales to format compatible with analysis
        # Use total_surface_area and grouped_price_per_sqm for correct calculations
        comparable_sales_for_analysis = []
        for sale in grouped_sales:
            # Create a compatible object for analysis
            class CompatibleSale:
                def __init__(self, grouped_sale):
                    self.sale_date = grouped_sale.sale_date
                    self.sale_price = grouped_sale.sale_price
                    self.surface_area = grouped_sale.total_surface_area
                    self.price_per_sqm = grouped_sale.grouped_price_per_sqm

            comparable_sales_for_analysis.append(CompatibleSale(sale))

        # Detect outliers using IQR method
        outlier_flags = dvf_service.detect_outliers_iqr(comparable_sales_for_analysis)

        # Calculate price analysis (excluding outliers by default)
        outlier_indices = [i for i, is_outlier in enumerate(outlier_flags) if is_outlier]
        analysis = dvf_service.calculate_price_analysis(
            asking_price=property.asking_price,
            surface_area=property.surface_area,
            comparable_sales=comparable_sales_for_analysis,
            exclude_indices=outlier_indices,
            apply_time_adjustment=False,  # Use raw prices for simple analysis
            locale=locale,
        )

        analysis["analysis_type"] = "simple"

        # Convert grouped sales to response format with multi-unit details
        comparable_sales_response = []
        for i, sale in enumerate(grouped_sales[:10]):
            sale_response = DVFGroupedTransactionResponse.from_orm(sale)
            sale_response.is_outlier = outlier_flags[i] if i < len(outlier_flags) else False
            sale_response.is_multi_unit = sale.unit_count > 1
            comparable_sales_response.append(sale_response)

    # Update property with analysis results
    property.estimated_value = analysis["estimated_value"]
    property.market_comparison_score = analysis["confidence_score"]
    property.recommendation = analysis["recommendation"]

    db.commit()

    return PriceAnalysisResponse(**analysis, comparable_sales=comparable_sales_response)


@router.post("/{property_id}/recalculate-analysis")
async def recalculate_analysis(
    property_id: int,
    request: Request,
    excluded_sale_ids: List[int],
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Recalculate price analysis excluding specific sales by their IDs.
    Used when user toggles outlier inclusion/exclusion checkboxes.
    """
    locale = get_local(request)

    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    # Get the latest analysis data from property (we need to know what sales were used)
    # Use GROUPED sales to match the original analysis
    grouped_sales = dvf_service.get_grouped_exact_address_sales(
        db=db,
        postal_code=property.postal_code or "",
        property_type=property.property_type or "Appartement",
        address=property.address or "",
    )

    if not grouped_sales:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("no_comparable_sales_short", locale),
        )

    # Convert grouped sales to compatible format
    comparable_sales_for_analysis = []
    for sale in grouped_sales:

        class CompatibleSale:
            def __init__(self, grouped_sale):
                self.id = grouped_sale.id
                self.sale_date = grouped_sale.sale_date
                self.sale_price = grouped_sale.sale_price
                self.surface_area = grouped_sale.total_surface_area
                self.price_per_sqm = grouped_sale.grouped_price_per_sqm

        comparable_sales_for_analysis.append(CompatibleSale(sale))

    # Build exclusion indices based on sale IDs
    sale_id_set = set(excluded_sale_ids)
    exclude_indices = [
        i for i, sale in enumerate(comparable_sales_for_analysis) if sale.id in sale_id_set
    ]

    # Recalculate analysis (use raw prices, no time adjustment for simple analysis)
    analysis = dvf_service.calculate_price_analysis(
        asking_price=property.asking_price,
        surface_area=property.surface_area,
        comparable_sales=comparable_sales_for_analysis,
        exclude_indices=exclude_indices,
        apply_time_adjustment=False,
        locale=locale,
    )

    # Log the calculated values for debugging
    print("🔍 RECALCULATE ANALYSIS:")
    print(f"   Excluded indices: {exclude_indices}")
    print(f"   Total sales: {len(comparable_sales_for_analysis)}")
    print(f"   Filtered sales: {len(comparable_sales_for_analysis) - len(exclude_indices)}")
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


@router.get("/{property_id}/market-trend")
async def get_market_trend(
    property_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Get year-over-year market trend data for visualization.
    Returns average price per m² by year with year-over-year change percentages.
    """
    locale = get_local(request)

    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    # Get all neighboring sales for trend (last 5 years)
    neighboring_sales = dvf_service.get_neighboring_sales_for_trend(
        db=db,
        postal_code=property.postal_code or "",
        property_type=property.property_type or "Appartement",
        surface_area=property.surface_area,
        address=property.address or "",
        months_back=60,  # 5 years
    )

    if not neighboring_sales:
        return {
            "years": [],
            "average_prices": [],
            "year_over_year_changes": [],
            "sample_counts": [],
            "total_sales": 0,
            "outliers_excluded": 0,
        }

    # CRITICAL: Detect and EXCLUDE outliers for consistent trend calculation
    outlier_flags = dvf_service.detect_outliers_iqr(neighboring_sales)
    filtered_sales = [sale for i, sale in enumerate(neighboring_sales) if not outlier_flags[i]]

    outliers_excluded = len(neighboring_sales) - len(filtered_sales)

    print(f"\n📊 MARKET TREND CHART for property {property_id}")
    print(f"   Total sales (5 years): {len(neighboring_sales)}")
    print(f"   Outliers detected: {outliers_excluded}")
    print(f"   Sales after filtering: {len(filtered_sales)}")

    # Group sales by year and calculate averages
    import statistics
    from collections import defaultdict

    sales_by_year = defaultdict(list)
    for sale in filtered_sales:  # Use filtered sales WITHOUT outliers
        if sale.sale_date and sale.price_per_sqm and sale.price_per_sqm > 0:
            year = sale.sale_date.year
            sales_by_year[year].append(sale.price_per_sqm)

    # Sort years
    sorted_years = sorted(sales_by_year.keys())

    # Calculate averages and YoY changes
    years = []
    average_prices = []
    year_over_year_changes = []
    sample_counts = []

    for i, year in enumerate(sorted_years):
        avg_price = statistics.mean(sales_by_year[year])
        years.append(year)
        average_prices.append(round(avg_price, 2))
        sample_counts.append(len(sales_by_year[year]))

        if i > 0:
            prev_avg = statistics.mean(sales_by_year[sorted_years[i - 1]])
            yoy_change = ((avg_price - prev_avg) / prev_avg) * 100
            year_over_year_changes.append(round(yoy_change, 2))
        else:
            year_over_year_changes.append(0)  # No change for first year

    # Extract street name for display
    from app.services.dvf_service import DVFService

    _, street_name = DVFService.extract_street_info(property.address or "")

    return {
        "years": years,
        "average_prices": average_prices,
        "year_over_year_changes": year_over_year_changes,
        "sample_counts": sample_counts,
        "street_name": street_name or property.address or "Unknown",
        "total_sales": len(neighboring_sales),
        "outliers_excluded": outliers_excluded,
    }


@router.post("/{property_id}/recalculate-trend")
async def recalculate_trend(
    property_id: int,
    request: Request,
    excluded_neighboring_sale_ids: List[int],
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Recalculate trend analysis excluding specific neighboring sales by their IDs.
    """
    locale = get_local(request)

    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("property_not_found", locale)
        )

    # Get GROUPED exact address sales (same as initial analysis)
    grouped_exact_sales = dvf_service.get_grouped_exact_address_sales(
        db=db,
        postal_code=property.postal_code or "",
        property_type=property.property_type or "Appartement",
        address=property.address or "",
    )

    # Convert to compatible format
    exact_sales = []
    for sale in grouped_exact_sales:

        class CompatibleSale:
            def __init__(self, grouped_sale):
                self.id = grouped_sale.id
                self.sale_date = grouped_sale.sale_date
                self.sale_price = grouped_sale.sale_price
                self.surface_area = grouped_sale.total_surface_area
                self.price_per_sqm = grouped_sale.grouped_price_per_sqm

        exact_sales.append(CompatibleSale(sale))

    # Get neighboring sales (ONLY 2024-2025, matching initial analysis)
    neighboring_sales = dvf_service.get_neighboring_sales_for_trend(
        db=db,
        postal_code=property.postal_code or "",
        property_type=property.property_type or "Appartement",
        surface_area=property.surface_area,
        address=property.address or "",
        months_back=24,  # Only current + past year
    )

    if not exact_sales and not neighboring_sales:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=translate("no_trend_sales", locale)
        )

    # Detect outliers in ALL neighboring sales
    neighboring_outlier_flags = dvf_service.detect_outliers_iqr(neighboring_sales)

    # Filter based on user selections (excluded_neighboring_sale_ids)
    excluded_id_set = set(excluded_neighboring_sale_ids)
    filtered_neighboring_sales = [
        sale for sale in neighboring_sales if sale.id not in excluded_id_set
    ]

    print(f"\n🔄 RECALCULATE TREND for property {property_id}")
    print(f"   Total neighboring sales: {len(neighboring_sales)}")
    print(f"   Excluded sale IDs: {excluded_id_set}")
    print(f"   Filtered neighboring sales: {len(filtered_neighboring_sales)}")

    # Recalculate trend projection with user-filtered sales
    trend_projection = dvf_service.calculate_trend_based_projection(
        exact_address_sales=exact_sales,
        neighboring_sales=filtered_neighboring_sales,  # Use filtered based on user choices
        surface_area=property.surface_area,
    )

    print(f"   Recalculated trend_used: {trend_projection.get('trend_used', 'N/A')}%")
    print(f"   Recalculated sample size: {trend_projection.get('trend_sample_size', 'N/A')}")

    # Include full neighboring sales list with outlier flags for UI
    trend_projection_with_sales = trend_projection.copy()
    trend_projection_with_sales["neighboring_sales"] = [
        {
            "id": sale.id,
            "address": sale.address,
            "sale_date": sale.sale_date.isoformat()
            if hasattr(sale.sale_date, "isoformat")
            else str(sale.sale_date),
            "sale_price": sale.sale_price,
            "surface_area": sale.surface_area,
            "price_per_sqm": sale.price_per_sqm,
            "is_outlier": neighboring_outlier_flags[i]
            if i < len(neighboring_outlier_flags)
            else False,
        }
        for i, sale in enumerate(neighboring_sales)
    ]

    # Return updated trend projection with sales list
    return {
        "trend_projection": trend_projection_with_sales,
        "neighboring_sales_count": len(filtered_neighboring_sales),
    }
