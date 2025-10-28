"""
DVF (Demandes de Valeurs Foncières) service for property price analysis.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
import statistics

from app.models.property import DVFRecord, Property


class DVFService:
    """Service for analyzing DVF data and providing price insights."""

    @staticmethod
    def get_comparable_sales(
        db: Session,
        postal_code: str,
        property_type: str,
        surface_area: float,
        radius_km: int = 2,
        months_back: int = 24,
        max_results: int = 20
    ) -> List[DVFRecord]:
        """
        Find comparable property sales from DVF data.

        Args:
            db: Database session
            postal_code: Property postal code
            property_type: Type of property (Appartement, Maison)
            surface_area: Property surface area in m²
            radius_km: Search radius (simplified: same postal code + nearby)
            months_back: How many months of historical data to consider
            max_results: Maximum number of results to return
        """
        cutoff_date = datetime.now() - timedelta(days=30 * months_back)

        # Surface area range (±30%)
        min_surface = surface_area * 0.7
        max_surface = surface_area * 1.3

        # Get the first two digits of postal code for department matching
        department = postal_code[:2] if postal_code else None

        query = db.query(DVFRecord).filter(
            and_(
                DVFRecord.sale_date >= cutoff_date,
                DVFRecord.property_type == property_type,
                DVFRecord.surface_area.between(min_surface, max_surface),
                or_(
                    DVFRecord.postal_code == postal_code,
                    DVFRecord.department == department
                )
            )
        ).order_by(DVFRecord.sale_date.desc()).limit(max_results)

        return query.all()

    @staticmethod
    def calculate_price_analysis(
        asking_price: float,
        surface_area: float,
        comparable_sales: List[DVFRecord]
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive price analysis based on comparable sales.
        """
        if not comparable_sales:
            return {
                "estimated_value": asking_price,
                "price_per_sqm": asking_price / surface_area if surface_area else 0,
                "market_avg_price_per_sqm": 0,
                "price_deviation_percent": 0,
                "recommendation": "Insufficient data",
                "confidence_score": 0,
            }

        # Calculate market statistics
        prices_per_sqm = [
            sale.price_per_sqm for sale in comparable_sales
            if sale.price_per_sqm and sale.price_per_sqm > 0
        ]

        if not prices_per_sqm:
            return {
                "estimated_value": asking_price,
                "price_per_sqm": asking_price / surface_area if surface_area else 0,
                "market_avg_price_per_sqm": 0,
                "price_deviation_percent": 0,
                "recommendation": "Insufficient data",
                "confidence_score": 0,
            }

        market_avg_price_per_sqm = statistics.mean(prices_per_sqm)
        market_median_price_per_sqm = statistics.median(prices_per_sqm)

        # Calculate estimated value
        estimated_value = market_median_price_per_sqm * surface_area
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

        # Confidence score based on number of comparables
        confidence_score = min(100, (len(comparable_sales) / max_results) * 100)

        return {
            "estimated_value": round(estimated_value, 2),
            "price_per_sqm": round(asking_price_per_sqm, 2),
            "market_avg_price_per_sqm": round(market_avg_price_per_sqm, 2),
            "market_median_price_per_sqm": round(market_median_price_per_sqm, 2),
            "price_deviation_percent": round(price_deviation_percent, 2),
            "recommendation": recommendation,
            "confidence_score": round(confidence_score, 2),
            "comparables_count": len(comparable_sales),
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
