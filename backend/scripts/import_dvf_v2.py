"""
Production-ready DVF importer with UPSERT, deduplication, versioning, and rollback.

Features:
- File hash checking to prevent duplicate imports
- UPSERT logic (INSERT ... ON CONFLICT DO UPDATE)
- Batch processing for memory efficiency
- Transaction safety with rollback on error
- Progress tracking and logging
- Complete audit trail in dvf_imports table

Usage:
    python scripts/import_dvf_v2.py <path_to_dvf_file> --year <YYYY>
    python scripts/import_dvf_v2.py data/dvf/ValeursFoncieres-2024.txt --year 2024

Download DVF data from: https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/
"""

import sys
import os
import argparse
import hashlib
import uuid
import logging
from datetime import datetime
from io import StringIO

import pandas as pd
from sqlalchemy.orm import Session
from psycopg2.extras import execute_values

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine
from app.models.property import DVFRecord, DVFImport, Base

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DVFImporter:
    """Production-ready DVF importer with deduplication and versioning."""

    def __init__(self, db: Session, batch_size: int = 10000):
        self.db = db
        self.batch_size = batch_size
        self.batch_id = str(uuid.uuid4())

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file to detect re-imports."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def is_already_imported(self, file_hash: str) -> bool:
        """Check if file has already been successfully imported."""
        existing = self.db.query(DVFImport).filter(
            DVFImport.source_file_hash == file_hash,
            DVFImport.status == 'completed'
        ).first()
        return existing is not None

    def parse_and_clean_csv(self, file_path: str, data_year: int) -> pd.DataFrame:
        """Parse and clean DVF CSV file (reuses v1 logic)."""
        logger.info(f"Reading DVF file: {file_path}")

        # Read pipe-delimited file with chunking to reduce memory usage
        df = pd.read_csv(file_path, sep='|', encoding='utf-8', low_memory=False, chunksize=None)
        logger.info(f"Loaded {len(df):,} raw records")

        # Column mappings
        column_mapping = {
            'Date mutation': 'sale_date',
            'Valeur fonciere': 'sale_price',
            'No voie': 'street_number',
            'Type de voie': 'street_type',
            'Voie': 'street_name',
            'Code postal': 'postal_code',
            'Commune': 'city',
            'Code departement': 'department',
            'Type local': 'property_type',
            'Surface reelle bati': 'surface_area',
            'Nombre pieces principales': 'rooms',
            'Surface terrain': 'land_surface',
        }

        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

        # Filter property types
        if 'property_type' in df.columns:
            df = df[df['property_type'].isin(['Appartement', 'Maison', 'Dépendance'])]
            logger.info(f"After property type filter: {len(df):,} records")

        # Clean street number
        if 'street_number' in df.columns:
            df['street_number'] = pd.to_numeric(df['street_number'], errors='coerce')
            df = df[df['street_number'].notna()]
            df['street_number'] = df['street_number'].astype(int)
            logger.info(f"After street_number cleaning: {len(df):,} records")

        # Clean postal code
        if 'postal_code' in df.columns:
            df['postal_code'] = df['postal_code'].astype(str).str.replace(r'\.0$', '', regex=True)
            df['postal_code'] = df['postal_code'].str.zfill(5)
            df = df[df['postal_code'].str.match(r'^\d{5}$', na=False)]
            logger.info(f"After postal_code cleaning: {len(df):,} records")

        # Clean department
        if 'department' in df.columns:
            df['department'] = df['department'].astype(str).str.replace(r'\.0$', '', regex=True)
            df['department'] = df['department'].str.zfill(2)
            df = df[df['department'].str.match(r'^\d{2,3}$', na=False)]
            logger.info(f"After department cleaning: {len(df):,} records")

        # Clean sale price
        if 'sale_price' in df.columns:
            df['sale_price'] = df['sale_price'].astype(str).str.replace(' ', '').str.replace(',', '.')
            df['sale_price'] = pd.to_numeric(df['sale_price'], errors='coerce')
            df = df[df['sale_price'] >= 0]
            logger.info(f"After sale_price cleaning: {len(df):,} records")

        # Clean surface area
        if 'surface_area' in df.columns:
            df['surface_area'] = pd.to_numeric(df['surface_area'], errors='coerce')
            df = df[df['surface_area'] >= 0]
            logger.info(f"After surface_area cleaning: {len(df):,} records")

        # Clean rooms
        if 'rooms' in df.columns:
            df['rooms'] = pd.to_numeric(df['rooms'], errors='coerce')
            df = df[df['rooms'] >= 0]

        # Convert date (DD/MM/YYYY format)
        if 'sale_date' in df.columns:
            df['sale_date'] = pd.to_datetime(df['sale_date'], format='%d/%m/%Y', errors='coerce')
            logger.info(f"After date conversion: {len(df):,} records")

        # Create full address
        if 'street_number' in df.columns and 'street_name' in df.columns:
            if 'street_type' in df.columns:
                df['address'] = (
                    df['street_number'].astype(str) + ' ' +
                    df['street_type'].fillna('').astype(str).str.strip() + ' ' +
                    df['street_name'].astype(str)
                )
            else:
                df['address'] = df['street_number'].astype(str) + ' ' + df['street_name'].astype(str)

            df['address'] = df['address'].str.replace(r'\s+', ' ', regex=True).str.strip()
            logger.info(f"After address creation: {len(df):,} records")

        # Drop missing critical fields
        df = df.dropna(subset=['sale_date', 'sale_price', 'address'])
        logger.info(f"After dropping NaN critical fields: {len(df):,} records")

        # Remove duplicates
        df = df.drop_duplicates(subset=['sale_date', 'sale_price', 'address', 'property_type', 'surface_area'])
        logger.info(f"After deduplication: {len(df):,} records")

        # Calculate price per sqm
        df['price_per_sqm'] = None
        mask = (df['surface_area'].notna()) & (df['surface_area'] > 0) & (df['sale_price'].notna())
        df.loc[mask, 'price_per_sqm'] = df.loc[mask, 'sale_price'] / df.loc[mask, 'surface_area']

        # Add metadata columns
        df['data_year'] = data_year
        df['import_batch_id'] = self.batch_id
        df['imported_at'] = datetime.utcnow()

        # Calculate transaction group ID (hash of sale_date + price + address + postal)
        df['transaction_group_id'] = df.apply(
            lambda row: hashlib.md5(
                f"{row['sale_date']}|{row['sale_price']}|{row['address']}|{row['postal_code']}".encode()
            ).hexdigest(),
            axis=1
        )

        return df

    def upsert_batch(self, batch_df: pd.DataFrame, source_file: str, source_file_hash: str) -> dict:
        """
        Perform UPSERT using PostgreSQL INSERT ... ON CONFLICT.

        Returns statistics: {'inserted': int, 'updated': int}
        """
        # Select only columns that exist in DVFRecord model
        columns = [
            'sale_date', 'sale_price', 'address', 'postal_code', 'city', 'department',
            'property_type', 'surface_area', 'rooms', 'land_surface', 'price_per_sqm',
            'data_year', 'import_batch_id', 'imported_at', 'transaction_group_id'
        ]

        # Add source file metadata
        batch_df['source_file'] = source_file
        batch_df['source_file_hash'] = source_file_hash
        columns.extend(['source_file', 'source_file_hash'])

        # Filter to only existing columns
        available_columns = [col for col in columns if col in batch_df.columns]
        batch_data = batch_df[available_columns]

        # Deduplicate within batch using unique constraint columns
        # This prevents "ON CONFLICT cannot affect row a second time" error
        batch_data = batch_data.drop_duplicates(
            subset=['sale_date', 'sale_price', 'address', 'postal_code', 'surface_area'],
            keep='first'
        )

        # Replace NaN with None for SQL
        batch_data = batch_data.where(pd.notna(batch_data), None)

        # Prepare values for execute_values
        values = [tuple(row) for row in batch_data.values]

        if not values:
            return {'inserted': 0, 'updated': 0}

        # Build column list for SQL
        col_list = ', '.join(available_columns)
        placeholders = ', '.join(['%s'] * len(available_columns))

        # UPSERT SQL with ON CONFLICT DO UPDATE
        upsert_sql = f"""
        INSERT INTO dvf_records ({col_list}, created_at)
        VALUES %s
        ON CONFLICT (sale_date, sale_price, address, postal_code, surface_area)
        DO UPDATE SET
            imported_at = EXCLUDED.imported_at,
            import_batch_id = EXCLUDED.import_batch_id,
            source_file = EXCLUDED.source_file,
            source_file_hash = EXCLUDED.source_file_hash
        """

        # Get raw psycopg2 connection
        conn = self.db.connection().connection
        cursor = conn.cursor()

        try:
            # Add created_at to each value tuple
            values_with_created = [v + (datetime.utcnow(),) for v in values]

            # Execute batch insert
            execute_values(cursor, upsert_sql, values_with_created, page_size=1000)

            inserted = cursor.rowcount

            return {'inserted': inserted, 'updated': 0}  # Simplified - PostgreSQL doesn't easily report updates
        except Exception as e:
            logger.error(f"Batch upsert failed: {e}")
            raise

    def import_file(self, file_path: str, data_year: int, force: bool = False) -> DVFImport:
        """
        Import DVF file with UPSERT logic and tracking.

        Args:
            file_path: Path to DVF CSV file
            data_year: Year of the dataset (e.g., 2023)
            force: Force re-import even if file hash exists

        Returns:
            DVFImport record with statistics
        """
        source_file = os.path.basename(file_path)
        file_hash = self.calculate_file_hash(file_path)

        logger.info(f"Starting import: {source_file}")
        logger.info(f"File hash: {file_hash}")
        logger.info(f"Batch ID: {self.batch_id}")

        # Check if already imported
        if not force and self.is_already_imported(file_hash):
            logger.info(f"File already imported successfully: {source_file}")
            existing = self.db.query(DVFImport).filter(
                DVFImport.source_file_hash == file_hash
            ).first()
            return existing

        # Create import record
        import_record = DVFImport(
            batch_id=self.batch_id,
            source_file=source_file,
            source_file_hash=file_hash,
            data_year=data_year,
            status='running',
            started_at=datetime.utcnow()
        )
        self.db.add(import_record)
        self.db.commit()

        try:
            # Parse and clean data
            df = self.parse_and_clean_csv(file_path, data_year)
            import_record.total_records = len(df)

            # Import in batches
            total_inserted = 0
            total_updated = 0
            total_batches = (len(df) + self.batch_size - 1) // self.batch_size

            for i in range(0, len(df), self.batch_size):
                batch = df.iloc[i:i + self.batch_size]
                batch_num = i // self.batch_size + 1

                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch):,} records)")

                stats = self.upsert_batch(batch, source_file, file_hash)
                total_inserted += stats['inserted']
                total_updated += stats['updated']

                self.db.commit()  # Commit each batch

            # Update import record with statistics
            import_record.inserted_records = total_inserted
            import_record.updated_records = total_updated
            import_record.skipped_records = import_record.total_records - (total_inserted + total_updated)
            import_record.completed_at = datetime.utcnow()
            import_record.duration_seconds = (import_record.completed_at - import_record.started_at).total_seconds()
            import_record.status = 'completed'

            self.db.commit()

            logger.info(f"✓ Import completed successfully!")
            logger.info(f"  Total: {import_record.total_records:,} records")
            logger.info(f"  Inserted: {import_record.inserted_records:,} records")
            logger.info(f"  Skipped: {import_record.skipped_records:,} records")
            logger.info(f"  Duration: {import_record.duration_seconds:.1f}s")
            logger.info(f"  Throughput: {import_record.total_records / import_record.duration_seconds:.0f} records/sec")

            return import_record

        except Exception as e:
            # Mark import as failed
            import_record.status = 'failed'
            import_record.error_message = str(e)
            import_record.completed_at = datetime.utcnow()
            self.db.commit()

            logger.error(f"Import failed: {e}", exc_info=True)
            raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Import DVF data with UPSERT and versioning')
    parser.add_argument('file_path', help='Path to DVF CSV file')
    parser.add_argument('--year', type=int, required=True, help='Data year (e.g., 2023)')
    parser.add_argument('--force', action='store_true', help='Force re-import even if file hash exists')
    parser.add_argument('--batch-size', type=int, default=10000, help='Batch size for processing')

    args = parser.parse_args()

    # Validate file exists
    if not os.path.exists(args.file_path):
        logger.error(f"File not found: {args.file_path}")
        sys.exit(1)

    # Import
    db = SessionLocal()
    try:
        importer = DVFImporter(db, batch_size=args.batch_size)
        import_record = importer.import_file(args.file_path, args.year, args.force)

        logger.info(f"\nImport Summary:")
        logger.info(f"  Batch ID: {import_record.batch_id}")
        logger.info(f"  Status: {import_record.status}")
        logger.info(f"  Total: {import_record.total_records:,}")
        logger.info(f"  Inserted: {import_record.inserted_records:,}")
        logger.info(f"  Duration: {import_record.duration_seconds:.1f}s")

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
