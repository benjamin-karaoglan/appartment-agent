"""
Script to import DVF (Demandes de Valeurs Foncières) data into the database.

Download DVF data from: https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/

Usage:
    python scripts/import_dvf.py <path_to_dvf_csv>
"""

import sys
import pandas as pd
from datetime import datetime
import json
from sqlalchemy.orm import Session

# Add parent directory to path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine
from app.models.property import DVFRecord, Base

# Create tables
Base.metadata.create_all(bind=engine)


def parse_dvf_csv(file_path: str) -> pd.DataFrame:
    """Parse DVF CSV file."""
    print(f"Reading DVF file: {file_path}")

    # Read pipe-delimited file with specific encoding
    df = pd.read_csv(file_path, sep='|', encoding='utf-8', low_memory=False)

    print(f"Loaded {len(df)} records")
    return df


def clean_and_transform(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and transform DVF data."""
    print("Cleaning and transforming data...")

    # DVF column mappings (matching actual file structure)
    column_mapping = {
        'Date mutation': 'sale_date',
        'Valeur fonciere': 'sale_price',
        'No voie': 'street_number',
        'Type de voie': 'street_type',  # RUE, AVENUE, BOULEVARD, etc.
        'Voie': 'street_name',
        'Code postal': 'postal_code',
        'Commune': 'city',
        'Code departement': 'department',
        'Type local': 'property_type',
        'Surface reelle bati': 'surface_area',
        'Nombre pieces principales': 'rooms',
        'Surface terrain': 'land_surface',
    }

    # Rename columns if they exist
    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    # Filter for apartments, houses, and Dépendance (often sold together with apartments)
    if 'property_type' in df.columns:
        df = df[df['property_type'].isin(['Appartement', 'Maison', 'Dépendance'])]

    print(f"After property type filter: {len(df)} records")

    # Clean street number - convert to int, remove .0 suffix
    # IMPORTANT: Do this BEFORE filtering by street_number to avoid losing records
    if 'street_number' in df.columns:
        df['street_number'] = pd.to_numeric(df['street_number'], errors='coerce')
        print(f"After street_number to numeric: {len(df)} records, NaN count: {df['street_number'].isna().sum()}")
        # Remove NaN street numbers
        df = df[df['street_number'].notna()]
        # Convert to int (removes .0) and keep as int
        df['street_number'] = df['street_number'].astype(int)
        print(f"After removing NaN street_numbers: {len(df)} records")

    # CRITICAL FIX: Clean postal code - keep as proper string format without .0 suffix
    if 'postal_code' in df.columns:
        # Convert to string and remove .0 suffix (e.g., "75006.0" -> "75006")
        df['postal_code'] = df['postal_code'].astype(str).str.replace(r'\.0$', '', regex=True)
        # Pad with zeros if needed (e.g., "1550" -> "01550")
        df['postal_code'] = df['postal_code'].str.zfill(5)
        # Filter valid 5-digit postal codes only
        df = df[df['postal_code'].str.match(r'^\d{5}$', na=False)]
        print(f"After postal_code cleaning: {len(df)} records")

    # Clean department code - keep as string without .0 suffix
    if 'department' in df.columns:
        df['department'] = df['department'].astype(str).str.replace(r'\.0$', '', regex=True)
        # Pad with zeros for single-digit departments (e.g., "1" -> "01")
        df['department'] = df['department'].str.zfill(2)
        # Filter valid 2-3 digit department codes
        df = df[df['department'].str.match(r'^\d{2,3}$', na=False)]
        print(f"After department cleaning: {len(df)} records")

    # Clean sale price (remove spaces and convert to float)
    if 'sale_price' in df.columns:
        df['sale_price'] = df['sale_price'].astype(str).str.replace(' ', '').str.replace(',', '.')
        df['sale_price'] = pd.to_numeric(df['sale_price'], errors='coerce')
        # Filter valid price range (>= 0 to handle all cases)
        df = df[df['sale_price'] >= 0]
        print(f"After sale_price cleaning: {len(df)} records")

    # Clean surface area
    if 'surface_area' in df.columns:
        df['surface_area'] = pd.to_numeric(df['surface_area'], errors='coerce')
        # Filter valid surface area (>= 0m² because Dépendance can have 0m²)
        df = df[df['surface_area'] >= 0]
        print(f"After surface_area cleaning: {len(df)} records")

    # Clean rooms count
    if 'rooms' in df.columns:
        df['rooms'] = pd.to_numeric(df['rooms'], errors='coerce')
        # Filter valid room count (>= 0 because Dépendance can have 0 rooms)
        df = df[df['rooms'] >= 0]
        print(f"After rooms cleaning: {len(df)} records")

    # Convert date - CRITICAL: DVF uses European format DD/MM/YYYY
    if 'sale_date' in df.columns:
        df['sale_date'] = pd.to_datetime(df['sale_date'], format='%d/%m/%Y', errors='coerce')
        print(f"After date conversion: {len(df)} records, NaN count: {df['sale_date'].isna().sum()}")

    # Create full address: Number + Type + Name (e.g., "56 RUE NOTRE-DAME DES CHAMPS")
    if 'street_number' in df.columns and 'street_name' in df.columns:
        if 'street_type' in df.columns:
            # Full address with type: "56 RUE NOTRE-DAME DES CHAMPS"
            df['address'] = (
                df['street_number'].astype(str) + ' ' +
                df['street_type'].fillna('').astype(str).str.strip() + ' ' +
                df['street_name'].astype(str)
            )
            # Clean up extra spaces
            df['address'] = df['address'].str.replace(r'\s+', ' ', regex=True).str.strip()
        else:
            # Fallback without type
            df['address'] = df['street_number'].astype(str) + ' ' + df['street_name'].astype(str)

        print(f"After address creation: {len(df)} records")

    # Drop rows with missing critical data
    print(f"Rows with NaN sale_date: {df['sale_date'].isna().sum()}")
    print(f"Rows with NaN sale_price: {df['sale_price'].isna().sum()}")
    print(f"Rows with NaN address: {df['address'].isna().sum()}")
    df = df.dropna(subset=['sale_date', 'sale_price', 'address'])
    print(f"After dropping NaN critical fields: {len(df)} records")

    # IMPORTANT: Remove duplicates BEFORE calculating price_per_sqm
    # When multiple properties are sold in one transaction (e.g., apartment + dépendance),
    # they have the same sale_date, sale_price, and address but different property_type and surface_area
    # We need to group them and calculate the total surface area first
    df = df.drop_duplicates(subset=['sale_date', 'sale_price', 'address', 'property_type', 'surface_area'], keep='first')

    # Calculate price per sqm AFTER handling duplicates
    # Note: For grouped transactions (apartment + dépendance), this will be done per property
    # which is not ideal but better than before. Ideally we should group by transaction ID.
    if 'sale_price' in df.columns and 'surface_area' in df.columns:
        # Only calculate for properties with surface_area > 0
        df['price_per_sqm'] = None
        mask = df['surface_area'] > 0
        df.loc[mask, 'price_per_sqm'] = df.loc[mask, 'sale_price'] / df.loc[mask, 'surface_area']

    print(f"After cleaning: {len(df)} records")
    return df


def import_to_database(df: pd.DataFrame):
    """Import cleaned data to database using PostgreSQL COPY (ultra-fast bulk insert)."""
    print("Importing to database using PostgreSQL COPY (ultra-fast)...")

    from app.core.database import engine
    import io
    from datetime import datetime

    # Prepare data
    print(f"Preparing {len(df):,} records for bulk insert...")
    df_copy = df.copy()

    # Convert datetime to date string for PostgreSQL
    df_copy['sale_date'] = df_copy['sale_date'].dt.strftime('%Y-%m-%d')

    # Convert rooms to integer (PostgreSQL expects INT not FLOAT)
    # Fill NaN with empty string which will become NULL
    df_copy['rooms'] = df_copy['rooms'].fillna(-1).astype(int)
    df_copy['rooms'] = df_copy['rooms'].replace(-1, pd.NA)

    # Add created_at timestamp
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    df_copy['created_at'] = now_str

    # Select columns in correct order for COPY
    columns_order = [
        'sale_date', 'sale_price', 'address', 'postal_code', 'city',
        'department', 'property_type', 'surface_area', 'rooms',
        'land_surface', 'price_per_sqm', 'created_at'
    ]

    df_export = df_copy[columns_order]

    # Convert to tab-separated format in memory (PostgreSQL COPY format)
    buffer = io.StringIO()
    df_export.to_csv(buffer, index=False, header=False, sep='\t', na_rep='\\N')
    buffer.seek(0)

    # Use raw PostgreSQL connection for COPY command
    print(f"Bulk inserting {len(df_export):,} records (this will be MUCH faster)...")
    connection = engine.raw_connection()

    try:
        cursor = connection.cursor()

        # PostgreSQL COPY command - up to 100x faster than row-by-row INSERT
        copy_sql = """
            COPY dvf_records (
                sale_date, sale_price, address, postal_code, city,
                department, property_type, surface_area, rooms,
                land_surface, price_per_sqm, created_at
            ) FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', NULL '\\N')
        """

        cursor.copy_expert(copy_sql, buffer)
        connection.commit()

        print(f"✓ Successfully imported {len(df_export):,} records!")

    except Exception as e:
        print(f"Error during bulk import: {e}")
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python import_dvf.py <path_to_dvf_csv>")
        print("\nDownload DVF data from:")
        print("https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/")
        sys.exit(1)

    csv_file = sys.argv[1]

    # Parse and clean data
    df = parse_dvf_csv(csv_file)
    df_clean = clean_and_transform(df)

    # Import to database
    import_to_database(df_clean)

    print("Import complete!")


if __name__ == "__main__":
    main()
