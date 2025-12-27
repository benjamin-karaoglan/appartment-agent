"""Unit tests for DVF service."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock
from app.services.dvf_service import DVFService
from app.models.property import DVFRecord


class TestExtractStreetInfo:
    """Test extract_street_info method."""

    def test_extract_valid_address(self):
        """Test extracting street number and name from valid address."""
        number, name = DVFService.extract_street_info("56 RUE NOTRE-DAME DES CHAMPS")
        assert number == 56
        assert name == "RUE NOTRE-DAME DES CHAMPS"

    def test_extract_address_with_bis(self):
        """Test extracting address with 'bis' suffix."""
        number, name = DVFService.extract_street_info("56 bis RUE NOTRE-DAME DES CHAMPS")
        assert number == 56
        assert name == "RUE NOTRE-DAME DES CHAMPS"

    def test_extract_address_with_lowercase(self):
        """Test extracting lowercase address."""
        number, name = DVFService.extract_street_info("18 rue jean mermoz")
        assert number == 18
        assert name == "RUE JEAN MERMOZ"

    def test_extract_address_no_number(self):
        """Test extracting address without number."""
        number, name = DVFService.extract_street_info("RUE NOTRE-DAME DES CHAMPS")
        assert number is None
        assert name is None

    def test_extract_empty_address(self):
        """Test extracting from empty address."""
        number, name = DVFService.extract_street_info("")
        assert number is None
        assert name is None

    def test_extract_none_address(self):
        """Test extracting from None address."""
        number, name = DVFService.extract_street_info(None)
        assert number is None
        assert name is None


class TestApplyTimeAdjustment:
    """Test apply_time_adjustment method."""

    def test_apply_positive_trend(self):
        """Test applying positive market trend."""
        # Sale from 1 year ago with 5% annual growth
        sale_date = datetime.now() - timedelta(days=365)
        adjusted = DVFService.apply_time_adjustment(10000, sale_date, 5.0)
        # Should be approximately 10500 (5% increase)
        assert 10400 < adjusted < 10600

    def test_apply_negative_trend(self):
        """Test applying negative market trend."""
        # Sale from 1 year ago with -5% annual decline
        sale_date = datetime.now() - timedelta(days=365)
        adjusted = DVFService.apply_time_adjustment(10000, sale_date, -5.0)
        # Should be approximately 9500 (5% decrease)
        assert 9400 < adjusted < 9600

    def test_apply_zero_trend(self):
        """Test with zero trend (no adjustment)."""
        sale_date = datetime.now() - timedelta(days=365)
        adjusted = DVFService.apply_time_adjustment(10000, sale_date, 0.0)
        assert adjusted == 10000

    def test_apply_with_date_object(self):
        """Test with date object instead of datetime."""
        # Test that date objects are handled correctly
        sale_date = date.today() - timedelta(days=365)
        adjusted = DVFService.apply_time_adjustment(10000, sale_date, 5.0)
        assert 10400 < adjusted < 10600

    def test_apply_with_none_date(self):
        """Test with None date (should return original price)."""
        adjusted = DVFService.apply_time_adjustment(10000, None, 5.0)
        assert adjusted == 10000


class TestCalculateMarketTrend:
    """Test calculate_market_trend method."""

    def test_calculate_trend_with_increasing_prices(self):
        """Test trend calculation with increasing prices."""
        # Create mock sales with increasing prices over 3 years
        sales = [
            Mock(sale_date=date(2022, 1, 1), price_per_sqm=10000),
            Mock(sale_date=date(2022, 6, 1), price_per_sqm=10100),
            Mock(sale_date=date(2023, 1, 1), price_per_sqm=10500),
            Mock(sale_date=date(2023, 6, 1), price_per_sqm=10600),
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=11000),
            Mock(sale_date=date(2024, 6, 1), price_per_sqm=11100),
        ]

        trend = DVFService.calculate_market_trend(sales)
        # Should show positive growth (approximately 5% per year)
        assert trend > 0

    def test_calculate_trend_with_decreasing_prices(self):
        """Test trend calculation with decreasing prices."""
        sales = [
            Mock(sale_date=date(2022, 1, 1), price_per_sqm=11000),
            Mock(sale_date=date(2023, 1, 1), price_per_sqm=10500),
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=10000),
        ]

        trend = DVFService.calculate_market_trend(sales)
        # Should show negative growth
        assert trend < 0

    def test_calculate_trend_insufficient_data(self):
        """Test with insufficient data (less than 2 sales)."""
        sales = [Mock(sale_date=date(2024, 1, 1), price_per_sqm=10000)]
        trend = DVFService.calculate_market_trend(sales)
        assert trend == 0.0

    def test_calculate_trend_single_year(self):
        """Test with all sales in same year."""
        sales = [
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=10000),
            Mock(sale_date=date(2024, 6, 1), price_per_sqm=10500),
            Mock(sale_date=date(2024, 12, 1), price_per_sqm=11000),
        ]

        trend = DVFService.calculate_market_trend(sales)
        # Should return 0 because need at least 2 different years
        assert trend == 0.0


class TestCalculatePriceAnalysis:
    """Test calculate_price_analysis method."""

    def test_analysis_with_comparable_sales(self):
        """Test price analysis with comparable sales."""
        # Create mock comparable sales
        comparable_sales = [
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=10000),
            Mock(sale_date=date(2024, 2, 1), price_per_sqm=10200),
            Mock(sale_date=date(2024, 3, 1), price_per_sqm=10100),
            Mock(sale_date=date(2024, 4, 1), price_per_sqm=9900),
            Mock(sale_date=date(2024, 5, 1), price_per_sqm=10300),
        ]

        analysis = DVFService.calculate_price_analysis(
            asking_price=650000,  # 65m² * 10000/m²
            surface_area=65,
            comparable_sales=comparable_sales
        )

        assert "estimated_value" in analysis
        assert "price_per_sqm" in analysis
        assert "market_avg_price_per_sqm" in analysis
        assert "market_median_price_per_sqm" in analysis
        assert "price_deviation_percent" in analysis
        assert "recommendation" in analysis
        assert "confidence_score" in analysis
        assert analysis["comparables_count"] == 5

    def test_analysis_fair_price(self):
        """Test analysis when price is fair."""
        comparable_sales = [
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=10000),
            Mock(sale_date=date(2024, 2, 1), price_per_sqm=10000),
        ]

        analysis = DVFService.calculate_price_analysis(
            asking_price=650000,  # 65m² * 10000/m² = exactly market
            surface_area=65,
            comparable_sales=comparable_sales
        )

        # Should be within -5% to +5% (fair price range)
        assert -5 <= analysis["price_deviation_percent"] <= 5

    def test_analysis_overpriced(self):
        """Test analysis when price is overpriced."""
        comparable_sales = [
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=10000),
            Mock(sale_date=date(2024, 2, 1), price_per_sqm=10000),
        ]

        analysis = DVFService.calculate_price_analysis(
            asking_price=780000,  # 65m² * 12000/m² = 20% above market
            surface_area=65,
            comparable_sales=comparable_sales
        )

        # Should show positive deviation (overpriced)
        assert analysis["price_deviation_percent"] > 10
        assert "overpriced" in analysis["recommendation"].lower()

    def test_analysis_underpriced(self):
        """Test analysis when price is below market."""
        comparable_sales = [
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=10000),
            Mock(sale_date=date(2024, 2, 1), price_per_sqm=10000),
        ]

        analysis = DVFService.calculate_price_analysis(
            asking_price=520000,  # 65m² * 8000/m² = 20% below market
            surface_area=65,
            comparable_sales=comparable_sales
        )

        # Should show negative deviation (good deal)
        assert analysis["price_deviation_percent"] < -10
        assert "deal" in analysis["recommendation"].lower()

    def test_analysis_no_sales(self):
        """Test analysis with no comparable sales."""
        analysis = DVFService.calculate_price_analysis(
            asking_price=650000,
            surface_area=65,
            comparable_sales=[]
        )

        assert analysis["recommendation"] == "Insufficient data"
        assert analysis["confidence_score"] == 0

    def test_median_price_calculation(self):
        """Test that median price is calculated correctly."""
        comparable_sales = [
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=8000),
            Mock(sale_date=date(2024, 2, 1), price_per_sqm=9000),
            Mock(sale_date=date(2024, 3, 1), price_per_sqm=10000),  # Median
            Mock(sale_date=date(2024, 4, 1), price_per_sqm=11000),
            Mock(sale_date=date(2024, 5, 1), price_per_sqm=12000),
        ]

        analysis = DVFService.calculate_price_analysis(
            asking_price=650000,
            surface_area=65,
            comparable_sales=comparable_sales
        )

        # Median should be 10000
        assert analysis["market_median_price_per_sqm"] == 10000


class TestCalculateTrendBasedProjection:
    """Test calculate_trend_based_projection method."""

    def test_projection_with_data(self):
        """Test projection with exact address and neighboring sales."""
        exact_sales = [
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=10000),
        ]

        neighboring_sales = [
            Mock(sale_date=date(2023, 1, 1), price_per_sqm=9000),
            Mock(sale_date=date(2024, 1, 1), price_per_sqm=10000),
        ]

        projection = DVFService.calculate_trend_based_projection(
            exact_address_sales=exact_sales,
            neighboring_sales=neighboring_sales,
            surface_area=65
        )

        assert "estimated_value_2025" in projection
        assert "trend_used" in projection
        assert "trend_source" in projection
        assert "base_sale_date" in projection
        assert projection["base_sale_date"] == date(2024, 1, 1)

    def test_projection_no_data(self):
        """Test projection with no data."""
        projection = DVFService.calculate_trend_based_projection(
            exact_address_sales=[],
            neighboring_sales=[],
            surface_area=65
        )

        assert projection["estimated_value_2025"] is None
        assert projection["trend_source"] == "insufficient_data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
