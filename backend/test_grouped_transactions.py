#!/usr/bin/env python3
"""
Test script to validate grouped transaction queries.
Tests the exact case from user: 56 RUE NOTRE-DAME DES CHAMPS
"""
import sys
sys.path.insert(0, '/Users/carrefour/appartment-agent/backend')

from app.core.database import SessionLocal
from app.services.dvf_service import DVFService
from app.models.property import DVFGroupedTransaction
import json

def test_grouped_exact_address():
    """Test grouped exact address sales for the multi-unit example."""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("Testing Grouped Transaction Query")
        print("=" * 80)
        print()

        # Test parameters from user's example
        postal_code = "75006"
        property_type = "Appartement"
        address = "56 RUE NOTRE-DAME DES CHAMPS"

        print(f"Query Parameters:")
        print(f"  Address: {address}")
        print(f"  Postal Code: {postal_code}")
        print(f"  Property Type: {property_type}")
        print()

        # Call the service method
        grouped_sales = DVFService.get_grouped_exact_address_sales(
            db=db,
            postal_code=postal_code,
            property_type=property_type,
            address=address,
            months_back=60,
            max_results=20
        )

        print(f"Results Found: {len(grouped_sales)}")
        print()

        if grouped_sales:
            for i, sale in enumerate(grouped_sales, 1):
                print(f"Transaction {i}:")
                print(f"  Transaction ID: {sale.transaction_group_id}")
                print(f"  Sale Date: {sale.sale_date}")
                print(f"  Sale Price: {sale.sale_price:,.0f} €")
                print(f"  Address: {sale.address}")
                print(f"  Total Surface: {sale.total_surface_area} m²")
                print(f"  Total Rooms: {sale.total_rooms}")
                print(f"  Unit Count: {sale.unit_count}")
                print(f"  Grouped Price/m²: {sale.grouped_price_per_sqm:,.2f} €/m²")
                print(f"  Is Multi-Unit: {sale.unit_count > 1}")

                # Parse and display lot details
                if sale.lots_detail:
                    lots = json.loads(sale.lots_detail) if isinstance(sale.lots_detail, str) else sale.lots_detail
                    print(f"  Lot Details:")
                    for j, lot in enumerate(lots, 1):
                        print(f"    Lot {j}:")
                        print(f"      ID: {lot.get('id')}")
                        print(f"      Surface: {lot.get('surface_area')} m²")
                        print(f"      Rooms: {lot.get('rooms')}")
                        print(f"      Individual Price/m²: {lot.get('price_per_sqm', 0):,.2f} €/m²")

                print()
        else:
            print("No results found!")

        print("=" * 80)
        print("VALIDATION:")
        print("=" * 80)
        if grouped_sales and grouped_sales[0].sale_date.strftime('%Y-%m-%d') == '2021-12-07':
            sale = grouped_sales[0]
            print("✓ Found the 2021-12-07 transaction")
            print(f"✓ Total Surface: {sale.total_surface_area} m² (Expected: 151.37 m²)")
            print(f"✓ Unit Count: {sale.unit_count} (Expected: 2)")
            print(f"✓ Grouped Price/m²: {sale.grouped_price_per_sqm:,.2f} €/m² (Expected: ~8,852 €/m²)")

            if sale.unit_count == 2 and sale.total_surface_area == 151.37:
                print()
                print("🎉 SUCCESS! Multi-unit transaction is correctly aggregated!")
                print(f"   - ONE transaction (not two separate sales)")
                print(f"   - Correct total surface: {sale.total_surface_area} m²")
                print(f"   - Correct price/m²: {sale.grouped_price_per_sqm:,.2f} €/m²")
            else:
                print()
                print("⚠️  WARNING: Values don't match expected!")
        else:
            print("❌ ERROR: Could not find the expected transaction!")

    finally:
        db.close()

if __name__ == "__main__":
    test_grouped_exact_address()
