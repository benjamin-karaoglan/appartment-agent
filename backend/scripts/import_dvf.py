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
sys.path.append('..')

from app.core.database import SessionLocal, engine
from app.models.property import DVFRecord, Base

# Create tables
Base.metadata.create_all(bind=engine)


def parse_dvf_csv(file_path: str) -> pd.DataFrame:
    """Parse DVF CSV file."""
    print(f"Reading CSV file: {file_path}")

    # Read CSV with specific encoding
    df = pd.read_csv(file_path, encoding='utf-8', low_memory=False)

    print(f"Loaded {len(df)} records")
    return df


def clean_and_transform(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and transform DVF data."""
    print("Cleaning and transforming data...")

    # Common DVF column mappings (adjust based on actual CSV structure)
    column_mapping = {
        'date_mutation': 'sale_date',
        'valeur_fonciere': 'sale_price',
        'adresse_numero': 'street_number',
        'adresse_nom_voie': 'street_name',
        'code_postal': 'postal_code',
        'commune': 'city',
        'code_departement': 'department',
        'type_local': 'property_type',
        'surface_reelle_bati': 'surface_area',
        'nombre_pieces_principales': 'rooms',
        'surface_terrain': 'land_surface',
    }

    # Rename columns if they exist
    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    # Filter for apartments and houses only
    if 'property_type' in df.columns:
        df = df[df['property_type'].isin(['Appartement', 'Maison'])]

    # Clean sale price (remove spaces and convert to float)
    if 'sale_price' in df.columns:
        df['sale_price'] = df['sale_price'].astype(str).str.replace(' ', '').str.replace(',', '.')
        df['sale_price'] = pd.to_numeric(df['sale_price'], errors='coerce')

    # Convert date
    if 'sale_date' in df.columns:
        df['sale_date'] = pd.to_datetime(df['sale_date'], errors='coerce')

    # Calculate price per sqm
    if 'sale_price' in df.columns and 'surface_area' in df.columns:
        df['price_per_sqm'] = df['sale_price'] / df['surface_area']

    # Create full address
    if 'street_number' in df.columns and 'street_name' in df.columns:
        df['address'] = df['street_number'].astype(str) + ' ' + df['street_name'].astype(str)

    # Drop rows with missing critical data
    df = df.dropna(subset=['sale_date', 'sale_price'])

    print(f"After cleaning: {len(df)} records")
    return df


def import_to_database(df: pd.DataFrame, batch_size: int = 1000):
    """Import cleaned data to database."""
    print("Importing to database...")

    db: Session = SessionLocal()

    try:
        records_imported = 0

        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i + batch_size]

            for _, row in batch.iterrows():
                try:
                    # Create DVF record
                    record = DVFRecord(
                        sale_date=row.get('sale_date'),
                        sale_price=row.get('sale_price'),
                        address=row.get('address', ''),
                        postal_code=row.get('postal_code', ''),
                        city=row.get('city', ''),
                        department=row.get('department', ''),
                        property_type=row.get('property_type', ''),
                        surface_area=row.get('surface_area'),
                        rooms=row.get('rooms'),
                        land_surface=row.get('land_surface'),
                        price_per_sqm=row.get('price_per_sqm'),
                        raw_data=json.dumps(row.to_dict(), default=str)
                    )

                    db.add(record)
                    records_imported += 1

                except Exception as e:
                    print(f"Error importing row: {e}")
                    continue

            # Commit batch
            db.commit()
            print(f"Imported {records_imported} records...")

        print(f"Successfully imported {records_imported} records!")

    except Exception as e:
        print(f"Error during import: {e}")
        db.rollback()
    finally:
        db.close()


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
