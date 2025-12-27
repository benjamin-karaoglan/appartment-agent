"""
DVF (Demandes de Valeurs Foncières) service for property price analysis.
"""

from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta, date
import statistics
import re

from app.models.property import DVFRecord, Property


class DVFService:
    """Service for analyzing DVF data and providing price insights."""

    @staticmethod
    def detect_outliers_iqr(sales: List[DVFRecord]) -> List[bool]:
        """
        Detect outliers using the IQR (Interquartile Range) method.

        Outliers are values that fall outside Q1 - 1.5*IQR or Q3 + 1.5*IQR.
        For small datasets (< 4 sales), uses mean ± 2*std deviation instead.

        Args:
            sales: List of DVF records

        Returns:
            List of boolean flags indicating whether each sale is an outlier
        """
        if len(sales) < 2:
            # Can't detect outliers with less than 2 data points
            return [False] * len(sales)

        # Extract price per sqm values
        prices_per_sqm = [sale.price_per_sqm for sale in sales if sale.price_per_sqm]

        if len(prices_per_sqm) < 2:
            return [False] * len(sales)

        # For small datasets (< 4), use mean ± 1.5*std deviation (more sensitive)
        if len(prices_per_sqm) < 4:
            mean = statistics.mean(prices_per_sqm)
            stdev = statistics.stdev(prices_per_sqm) if len(prices_per_sqm) > 1 else 0
            lower_bound = mean - 1.5 * stdev
            upper_bound = mean + 1.5 * stdev

            outlier_flags = []
            for sale in sales:
                if sale.price_per_sqm:
                    is_outlier = sale.price_per_sqm < lower_bound or sale.price_per_sqm > upper_bound
                    outlier_flags.append(is_outlier)
                else:
                    outlier_flags.append(False)
            return outlier_flags

        # Calculate quartiles
        sorted_prices = sorted(prices_per_sqm)
        q1 = statistics.quantiles(sorted_prices, n=4)[0]  # 25th percentile
        q3 = statistics.quantiles(sorted_prices, n=4)[2]  # 75th percentile
        iqr = q3 - q1

        # Calculate outlier bounds
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        # Flag outliers
        outlier_flags = []
        for sale in sales:
            if sale.price_per_sqm:
                is_outlier = sale.price_per_sqm < lower_bound or sale.price_per_sqm > upper_bound
                outlier_flags.append(is_outlier)
            else:
                outlier_flags.append(False)

        return outlier_flags

    @staticmethod
    def extract_street_info(address: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Extract street number and street name from address.

        Returns:
            Tuple of (street_number, street_name)
        """
        if not address:
            return None, None

        # Try to extract street number (handle formats like "56", "56 bis", "56-58")
        match = re.match(r'^(\d+)(?:\s*(?:bis|ter|quater|[A-Z])?)?\s+(.+)$', address.strip(), re.IGNORECASE)
        if match:
            try:
                street_number = int(match.group(1))
                street_name = match.group(2).strip().upper()
                return street_number, street_name
            except (ValueError, AttributeError):
                pass

        return None, None

    @staticmethod
    def get_exact_address_sales(
        db: Session,
        postal_code: str,
        property_type: str,
        address: str,
        months_back: int = 60,
        max_results: int = 20
    ) -> List[DVFRecord]:
        """
        Get sales for the EXACT address only, no neighbors or fallbacks.
        Used for simple analysis to show only the building's history.

        Args:
            db: Database session
            postal_code: Property postal code
            property_type: Type of property (Appartement, Maison)
            address: Property address for exact matching
            months_back: How many months of historical data to consider
            max_results: Maximum number of results to return

        Returns:
            List of DVF records at the exact address, or empty list if none found
        """
        cutoff_date = datetime.now() - timedelta(days=30 * months_back)

        # Extract street information
        street_number, street_name = DVFService.extract_street_info(address)

        if not street_number or not street_name:
            return []

        # Query for exact address matches only
        exact_query = db.query(DVFRecord).filter(
            DVFRecord.sale_date >= cutoff_date,
            DVFRecord.property_type == property_type,
            DVFRecord.surface_area.isnot(None),
            DVFRecord.price_per_sqm.isnot(None),
            DVFRecord.price_per_sqm > 0,
            DVFRecord.postal_code == postal_code,
            DVFRecord.address.ilike(f'{street_number} {street_name}%')
        ).order_by(DVFRecord.sale_date.desc()).limit(max_results)

        return exact_query.all()

    @staticmethod
    def get_comparable_sales(
        db: Session,
        postal_code: str,
        property_type: str,
        surface_area: float,
        address: str = "",
        radius_km: int = 2,
        months_back: int = 60,  # CHANGED: 60 months = 5 years to include 2022-2025
        max_results: int = 20
    ) -> List[DVFRecord]:
        """
        Find comparable property sales from DVF data with smart address-based matching.

        Priority order:
        1. Same exact address (same building)
        2. Neighboring addresses (±2, ±4, ±6, ±8 on same street)
        3. Same street (broader range)
        4. Same postal code (fallback)

        Args:
            db: Database session
            postal_code: Property postal code
            property_type: Type of property (Appartement, Maison)
            surface_area: Property surface area in m²
            address: Property address for precise matching
            radius_km: Search radius (not used in current implementation)
            months_back: How many months of historical data to consider
            max_results: Maximum number of results to return
        """
        cutoff_date = datetime.now() - timedelta(days=30 * months_back)

        # Surface area range (±30%)
        min_surface = surface_area * 0.7
        max_surface = surface_area * 1.3

        # Extract street information
        street_number, street_name = DVFService.extract_street_info(address)

        # Base filters WITHOUT surface area (for exact address matches)
        base_filters_no_surface = and_(
            DVFRecord.sale_date >= cutoff_date,
            DVFRecord.property_type == property_type,
            DVFRecord.surface_area.isnot(None),
            DVFRecord.price_per_sqm.isnot(None),
            DVFRecord.price_per_sqm > 0,
            DVFRecord.postal_code == postal_code
        )

        # Base filters WITH surface area tolerance (for neighboring/broader searches)
        base_filters_with_surface = and_(
            base_filters_no_surface,
            DVFRecord.surface_area.between(min_surface, max_surface)
        )

        # CRITICAL CHANGE: Exact address matches ignore surface area filter
        # This ensures sales at the exact address ALWAYS appear, regardless of size differences
        # But we also include neighboring sales for context if the surface areas don't match

        exact_results = []

        # Try to find exact address matches first (WITHOUT surface area filter)
        if street_number and street_name:
            exact_query = db.query(DVFRecord).filter(
                base_filters_no_surface,
                DVFRecord.address.ilike(f'{street_number} {street_name}%')
            ).order_by(DVFRecord.sale_date.desc()).limit(max_results)
            exact_results = exact_query.all()

        # If we have exact address sales AND they match the surface area criteria,
        # return ONLY those (original behavior)
        if exact_results:
            # Check if at least one exact result matches the surface area range
            has_matching_surface = any(
                min_surface <= sale.surface_area <= max_surface
                for sale in exact_results
            )

            if has_matching_surface or len(exact_results) >= 3:
                # Either we have good surface matches OR we have 3+ sales at exact address
                # In both cases, return only exact address sales
                return exact_results[:max_results]

            # Otherwise, we have exact address sales but they don't match surface area well
            # Keep them at the TOP but also add neighboring sales for better comparison context
            results = list(exact_results)
        else:
            # No exact address sales, start with empty list
            results = []

        # Priority 2: Neighboring addresses (WITH surface area filter)
        if street_number and street_name:
            # Generate neighbor addresses (±2, ±4, ±6, ±8, ±10)
            neighbors = []
            for offset in [2, 4, 6, 8, 10]:
                neighbors.append(street_number + offset)
                if street_number - offset > 0:
                    neighbors.append(street_number - offset)

            neighbor_conditions = [
                DVFRecord.address.ilike(f'{num} {street_name}%')
                for num in neighbors
            ]

            neighbor_query = db.query(DVFRecord).filter(
                base_filters_with_surface,
                or_(*neighbor_conditions)
            ).order_by(DVFRecord.sale_date.desc()).limit(max_results - len(results))

            neighbor_results = neighbor_query.all()
            # Avoid duplicates (though shouldn't happen since exact address doesn't match surface filter)
            existing_ids = {r.id for r in results}
            results.extend([r for r in neighbor_results if r.id not in existing_ids])

        # Priority 3: Same street (broader range, WITH surface area filter)
        if len(results) < 5 and street_name:
            street_query = db.query(DVFRecord).filter(
                base_filters_with_surface,
                DVFRecord.address.ilike(f'%{street_name}%')
            ).order_by(DVFRecord.sale_date.desc()).limit(max_results - len(results))

            street_results = street_query.all()
            # Avoid duplicates
            existing_ids = {r.id for r in results}
            results.extend([r for r in street_results if r.id not in existing_ids])

        # Priority 4: Fallback to same postal code (WITH surface area filter)
        if len(results) < 5:
            fallback_query = db.query(DVFRecord).filter(
                base_filters_with_surface
            ).order_by(DVFRecord.sale_date.desc()).limit(max_results - len(results))

            fallback_results = fallback_query.all()
            # Avoid duplicates
            existing_ids = {r.id for r in results}
            results.extend([r for r in fallback_results if r.id not in existing_ids])

        # Sort results, but keep exact address matches at the top
        if exact_results:
            # Split into exact and non-exact
            exact_ids = {r.id for r in exact_results}
            exact_list = [r for r in results if r.id in exact_ids]
            non_exact_list = [r for r in results if r.id not in exact_ids]

            # Sort each group by date
            exact_list.sort(key=lambda x: x.sale_date, reverse=True)
            non_exact_list.sort(key=lambda x: x.sale_date, reverse=True)

            # Combine: exact addresses first, then others
            results = exact_list + non_exact_list
        else:
            # No exact addresses, just sort by date
            results.sort(key=lambda x: x.sale_date, reverse=True)

        return results[:max_results]

    @staticmethod
    def get_neighboring_sales_for_trend(
        db: Session,
        postal_code: str,
        property_type: str,
        surface_area: float,
        address: str,
        months_back: int = 48,
        max_results: int = 200  # Increased to get ALL sales on the street
    ) -> List[DVFRecord]:
        """
        Get neighboring address sales for trend calculation.
        Used when exact address doesn't have enough historical data.

        Returns sales from neighboring addresses (±2, ±4, ±6, ±8, ±10) and same street.
        NO surface area filter - we want all sales to calculate accurate trends.
        """
        street_number, street_name = DVFService.extract_street_info(address)

        if not street_number or not street_name:
            return []

        cutoff_date = datetime.now() - timedelta(days=30 * months_back)

        # NO surface area filter for trend analysis - use ALL sales on the street
        base_filters = and_(
            DVFRecord.sale_date >= cutoff_date,
            DVFRecord.property_type == property_type,
            DVFRecord.surface_area.isnot(None),
            DVFRecord.price_per_sqm.isnot(None),
            DVFRecord.price_per_sqm > 0,
            DVFRecord.postal_code == postal_code
        )

        # Get neighboring addresses
        neighbors = []
        for offset in [2, 4, 6, 8, 10]:
            neighbors.append(street_number + offset)
            if street_number - offset > 0:
                neighbors.append(street_number - offset)

        neighbor_conditions = [
            DVFRecord.address.ilike(f'{num} {street_name}%')
            for num in neighbors
        ]

        # Also include same street for broader trend
        neighbor_conditions.append(DVFRecord.address.ilike(f'%{street_name}%'))

        query = db.query(DVFRecord).filter(
            base_filters,
            or_(*neighbor_conditions)
        ).order_by(DVFRecord.sale_date.desc()).limit(max_results)

        return query.all()

    @staticmethod
    def calculate_market_trend(comparable_sales: List[DVFRecord]) -> float:
        """
        Calculate market trend (annual price increase/decrease percentage).

        Returns:
            Annual trend as percentage (e.g., 5.0 for +5% per year)
        """
        if len(comparable_sales) < 2:
            return 0.0

        # Group sales by year
        sales_by_year = {}
        for sale in comparable_sales:
            if sale.sale_date and sale.price_per_sqm and sale.price_per_sqm > 0:
                year = sale.sale_date.year
                if year not in sales_by_year:
                    sales_by_year[year] = []
                sales_by_year[year].append(sale.price_per_sqm)

        # Need at least 2 different years
        if len(sales_by_year) < 2:
            return 0.0

        # Calculate average price per year
        year_averages = {
            year: statistics.mean(prices)
            for year, prices in sales_by_year.items()
        }

        # Sort by year
        sorted_years = sorted(year_averages.keys())

        # Calculate year-over-year changes
        yoy_changes = []
        for i in range(1, len(sorted_years)):
            prev_year = sorted_years[i-1]
            curr_year = sorted_years[i]
            years_diff = curr_year - prev_year

            if years_diff > 0 and year_averages[prev_year] > 0:
                price_change = year_averages[curr_year] - year_averages[prev_year]
                annual_change_pct = (price_change / year_averages[prev_year]) / years_diff * 100
                yoy_changes.append(annual_change_pct)

        # Return average annual trend
        return statistics.mean(yoy_changes) if yoy_changes else 0.0

    @staticmethod
    def apply_time_adjustment(
        price_per_sqm: float,
        sale_date: Union[datetime, date],
        trend_pct: float
    ) -> float:
        """
        Adjust historical price to current value using trend.

        Args:
            price_per_sqm: Historical price per sqm
            sale_date: Date of the historical sale (datetime or date)
            trend_pct: Annual trend percentage

        Returns:
            Adjusted price per sqm for current date
        """
        if not sale_date or trend_pct == 0:
            return price_per_sqm

        # Convert date to datetime if needed for calculation
        if isinstance(sale_date, date) and not isinstance(sale_date, datetime):
            sale_datetime = datetime.combine(sale_date, datetime.min.time())
        else:
            sale_datetime = sale_date

        # Calculate years between sale and now
        years_diff = (datetime.now() - sale_datetime).days / 365.25

        # Apply compound annual growth
        adjustment_factor = (1 + trend_pct / 100) ** years_diff

        return price_per_sqm * adjustment_factor

    @staticmethod
    def calculate_trend_based_projection(
        exact_address_sales: List[DVFRecord],
        neighboring_sales: List[DVFRecord],
        surface_area: float
    ) -> Dict[str, Any]:
        """
        Calculate 2025 price projection using trend from neighboring addresses.

        This is used when:
        - Exact address has historical sales (e.g., 2024) but not current
        - Need to project 2025 value using trends from neighboring addresses

        Logic:
        1. Take the most recent exact address sale price
        2. Calculate trend from neighboring addresses
        3. Apply that trend to project to 2025
        """
        if not exact_address_sales or not neighboring_sales:
            return {
                "estimated_value_2025": None,
                "trend_used": 0,
                "trend_source": "insufficient_data",
                "base_sale_date": None,
                "base_price_per_sqm": None
            }

        # Get most recent exact address sale
        exact_address_sales.sort(key=lambda x: x.sale_date, reverse=True)
        base_sale = exact_address_sales[0]

        # Calculate trend from neighboring addresses
        trend_pct = DVFService.calculate_market_trend(neighboring_sales)

        if abs(trend_pct) < 0.1:  # No significant trend
            # Use base sale price without adjustment
            return {
                "estimated_value_2025": base_sale.price_per_sqm * surface_area,
                "trend_used": 0,
                "trend_source": "no_significant_trend",
                "base_sale_date": base_sale.sale_date,
                "base_price_per_sqm": base_sale.price_per_sqm
            }

        # Project to 2025
        projected_price_per_sqm = DVFService.apply_time_adjustment(
            base_sale.price_per_sqm,
            base_sale.sale_date,
            trend_pct
        )

        return {
            "estimated_value_2025": projected_price_per_sqm * surface_area,
            "projected_price_per_sqm": projected_price_per_sqm,
            "trend_used": trend_pct,
            "trend_source": "neighboring_addresses",
            "base_sale_date": base_sale.sale_date,
            "base_price_per_sqm": base_sale.price_per_sqm,
            "trend_sample_size": len(neighboring_sales)
        }

    @staticmethod
    def calculate_price_analysis(
        asking_price: float,
        surface_area: float,
        comparable_sales: List[DVFRecord],
        exclude_indices: Optional[List[int]] = None,
        apply_time_adjustment: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive price analysis based on comparable sales.

        Args:
            asking_price: The asking price for the property
            surface_area: Surface area in m²
            comparable_sales: List of comparable sales
            exclude_indices: Optional list of indices to exclude from calculation (for outliers)
            apply_time_adjustment: Whether to adjust prices for time (default False for simple analysis)
        """
        if not comparable_sales:
            return {
                "estimated_value": asking_price,
                "price_per_sqm": asking_price / surface_area if surface_area else 0,
                "market_avg_price_per_sqm": 0,
                "price_deviation_percent": 0,
                "recommendation": "Insufficient data",
                "confidence_score": 0,
                "market_trend_annual": 0,
            }

        # Filter out excluded indices
        exclude_set = set(exclude_indices or [])
        filtered_sales = [sale for i, sale in enumerate(comparable_sales) if i not in exclude_set]

        if not filtered_sales:
            return {
                "estimated_value": asking_price,
                "price_per_sqm": asking_price / surface_area if surface_area else 0,
                "market_avg_price_per_sqm": 0,
                "price_deviation_percent": 0,
                "recommendation": "Insufficient data (all sales excluded)",
                "confidence_score": 0,
                "market_trend_annual": 0,
            }

        # Calculate market trend using filtered sales
        market_trend = DVFService.calculate_market_trend(filtered_sales)

        # Build price list - apply time adjustment only if requested
        adjusted_prices = []
        for sale in filtered_sales:
            if sale.price_per_sqm and sale.price_per_sqm > 0:
                if apply_time_adjustment and abs(market_trend) > 0.5:
                    # Apply time adjustment to project old prices to current value
                    adjusted_price = DVFService.apply_time_adjustment(
                        sale.price_per_sqm,
                        sale.sale_date,
                        market_trend
                    )
                else:
                    # Use raw price per sqm (no adjustment)
                    adjusted_price = sale.price_per_sqm
                adjusted_prices.append(adjusted_price)

        if not adjusted_prices:
            return {
                "estimated_value": asking_price,
                "price_per_sqm": asking_price / surface_area if surface_area else 0,
                "market_avg_price_per_sqm": 0,
                "price_deviation_percent": 0,
                "recommendation": "Insufficient data",
                "confidence_score": 0,
                "market_trend_annual": 0,
            }

        market_avg_price_per_sqm = statistics.mean(adjusted_prices)
        market_median_price_per_sqm = statistics.median(adjusted_prices)

        # Calculate estimated value using MEAN (average), not median
        # This ensures: estimated_value = market_avg_price_per_sqm * surface_area
        estimated_value = market_avg_price_per_sqm * surface_area
        asking_price_per_sqm = asking_price / surface_area if surface_area else 0

        # Calculate deviation
        price_deviation_percent = (
            ((asking_price_per_sqm - market_avg_price_per_sqm) / market_avg_price_per_sqm) * 100
            if market_avg_price_per_sqm > 0 else 0
        )

        # Generate recommendation
        if price_deviation_percent < -10:
            recommendation = "Excellent deal - Below market price"
        elif price_deviation_percent < -5:
            recommendation = "Good deal - Slightly below market"
        elif price_deviation_percent < 5:
            recommendation = "Fair price - At market value"
        elif price_deviation_percent < 10:
            recommendation = "Slightly overpriced - Room for negotiation"
        elif price_deviation_percent < 20:
            recommendation = "Overpriced - Significant negotiation needed"
        else:
            recommendation = "Heavily overpriced - Reconsider or negotiate heavily"

        # Confidence score based on number of comparables (20 is ideal)
        confidence_score = min(100, (len(filtered_sales) / 20) * 100)

        return {
            "estimated_value": round(estimated_value, 2),
            "price_per_sqm": round(asking_price_per_sqm, 2),
            "market_avg_price_per_sqm": round(market_avg_price_per_sqm, 2),
            "market_median_price_per_sqm": round(market_median_price_per_sqm, 2),
            "price_deviation_percent": round(price_deviation_percent, 2),
            "recommendation": recommendation,
            "confidence_score": round(confidence_score, 2),
            "comparables_count": len(filtered_sales),  # Use filtered_sales, not comparable_sales
            "market_trend_annual": round(market_trend, 2),
        }

    @staticmethod
    def calculate_investment_score(
        property_data: Property,
        price_analysis: Dict[str, Any],
        annual_costs: float,
        risk_factors: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate overall investment score and metrics.
        """
        # Value score (based on price vs market)
        price_deviation = price_analysis.get("price_deviation_percent", 0)
        if price_deviation < -10:
            value_score = 100
        elif price_deviation < 0:
            value_score = 80 + (abs(price_deviation) * 2)
        elif price_deviation < 10:
            value_score = 70 - (price_deviation * 3)
        else:
            value_score = max(0, 50 - (price_deviation - 10) * 2)

        # Risk score (lower is better, so we invert it)
        risk_penalty = len(risk_factors) * 15
        risk_score = max(0, 100 - risk_penalty)

        # Cost score (based on annual costs vs property value)
        if property_data.asking_price:
            cost_ratio = (annual_costs / property_data.asking_price) * 100
            if cost_ratio < 2:
                cost_score = 100
            elif cost_ratio < 3:
                cost_score = 80
            elif cost_ratio < 4:
                cost_score = 60
            else:
                cost_score = max(0, 50 - (cost_ratio - 4) * 10)
        else:
            cost_score = 50

        # Overall investment score (weighted average)
        investment_score = (
            value_score * 0.4 +
            risk_score * 0.3 +
            cost_score * 0.3
        )

        # Overall recommendation
        if investment_score >= 80:
            overall_recommendation = "Highly Recommended"
        elif investment_score >= 65:
            overall_recommendation = "Recommended with minor reservations"
        elif investment_score >= 50:
            overall_recommendation = "Proceed with caution"
        else:
            overall_recommendation = "Not recommended"

        return {
            "investment_score": round(investment_score, 2),
            "value_score": round(value_score, 2),
            "risk_score": round(risk_score, 2),
            "cost_score": round(cost_score, 2),
            "overall_recommendation": overall_recommendation,
        }


# Singleton instance
dvf_service = DVFService()
