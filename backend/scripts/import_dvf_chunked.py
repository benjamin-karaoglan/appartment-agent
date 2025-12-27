"""
Memory-efficient DVF importer using chunked CSV reading.

This version processes large DVF files in chunks to avoid memory exhaustion.

Usage:
    python scripts/import_dvf_chunked.py <path_to_dvf_file> --year <YYYY>
    python scripts/import_dvf_chunked.py data/dvf/ValeursFoncieres-2024.txt --year 2024
"""

import sys
import os
import argparse
import hashlib
import uuid
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session
from psycopg2.extras import execute_values

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.property import DVFRecord, DVFImport

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChunkedDVFImporter:
    """Memory-efficient DVF importer that processes CSV in chunks."""

    def __init__(self, db: Session, read_chunk_size: int = 50000, write_batch_size: int = 10000):
        self.db = db
        self.read_chunk_size = read_chunk_size  # Read CSV in chunks of this size
        self.write_batch_size = write_batch_size  # Write to DB in batches of this size
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

    def clean_chunk(self, chunk_df: pd.DataFrame, data_year: int) -> pd.DataFrame:
        """Apply cleaning and transformation logic to a chunk of data."""

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

        df = chunk_df.rename(columns={k: v for k, v in column_mapping.items() if k in chunk_df.columns})

        # Filter property types
        if 'property_type' in df.columns:
            df = df[df['property_type'].isin(['Appartement', 'Maison', 'Dépendance'])]

        # Clean street number
        if 'street_number' in df.columns:
            df['street_number'] = pd.to_numeric(df['street_number'], errors='coerce')
            df = df[df['street_number'].notna()]
            df['street_number'] = df['street_number'].astype(int)

        # Clean postal code
        if 'postal_code' in df.columns:
            df['postal_code'] = df['postal_code'].astype(str).str.replace(r'\.0$', '', regex=True)
            df['postal_code'] = df['postal_code'].str.zfill(5)
            df = df[df['postal_code'].str.match(r'^\d{5}$', na=False)]

        # Clean department
        if 'department' in df.columns:
            df['department'] = df['department'].astype(str).str.replace(r'\.0$', '', regex=True)
            df['department'] = df['department'].str.zfill(2)
            df = df[df['department'].str.match(r'^\d{2,3}$', na=False)]

        # Clean sale price
        if 'sale_price' in df.columns:
            df['sale_price'] = df['sale_price'].astype(str).str.replace(' ', '').str.replace(',', '.')
            df['sale_price'] = pd.to_numeric(df['sale_price'], errors='coerce')
            df = df[df['sale_price'] >= 0]

        # Clean surface area
        if 'surface_area' in df.columns:
            df['surface_area'] = pd.to_numeric(df['surface_area'], errors='coerce')
            df = df[df['surface_area'] >= 0]

        # Clean rooms
        if 'rooms' in df.columns:
            df['rooms'] = pd.to_numeric(df['rooms'], errors='coerce')
            df = df[df['rooms'] >= 0]

        # Convert date (DD/MM/YYYY format)
        if 'sale_date' in df.columns:
            df['sale_date'] = pd.to_datetime(df['sale_date'], format='%d/%m/%Y', errors='coerce')

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

        # Drop missing critical fields
        df = df.dropna(subset=['sale_date', 'sale_price', 'address'])

        # Remove duplicates within chunk
        df = df.drop_duplicates(subset=['sale_date', 'sale_price', 'address', 'property_type', 'surface_area'])

        # Calculate price per sqm
        df['price_per_sqm'] = None
        mask = (df['surface_area'].notna()) & (df['surface_area'] > 0) & (df['sale_price'].notna())
        df.loc[mask, 'price_per_sqm'] = df.loc[mask, 'sale_price'] / df.loc[mask, 'surface_area']

        # Add metadata columns
        df['data_year'] = data_year
        df['import_batch_id'] = self.batch_id
        df['imported_at'] = datetime.utcnow()

        # Calculate transaction group ID
        df['transaction_group_id'] = df.apply(
            lambda row: hashlib.md5(
                f"{row['sale_date']}|{row['sale_price']}|{row['address']}|{row['postal_code']}".encode()
            ).hexdigest(),
            axis=1
        )

        return df

    def upsert_batch(self, batch_df: pd.DataFrame, source_file: str, source_file_hash: str) -> dict:
        """Perform UPSERT using PostgreSQL INSERT ... ON CONFLICT."""

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

        # Deduplicate within batch
        batch_data = batch_data.drop_duplicates(
            subset=['sale_date', 'sale_price', 'address', 'postal_code', 'surface_area'],
            keep='first'
        )

        # Replace NaN with None
        batch_data = batch_data.where(pd.notna(batch_data), None)

        # Prepare values
        values = [tuple(row) for row in batch_data.values]

        if not values:
            return {'inserted': 0, 'updated': 0}

        # Build SQL
        col_list = ', '.join(available_columns)

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

            return {'inserted': inserted, 'updated': 0}
        except Exception as e:
            logger.error(f"Batch upsert failed: {e}")
            raise

    def import_file(self, file_path: str, data_year: int, force: bool = False) -> DVFImport:
        """Import DVF file with chunked reading for memory efficiency."""

        source_file = os.path.basename(file_path)
        file_hash = self.calculate_file_hash(file_path)

        logger.info(f"Starting chunked import: {source_file}")
        logger.info(f"File hash: {file_hash}")
        logger.info(f"Batch ID: {self.batch_id}")
        logger.info(f"Read chunk size: {self.read_chunk_size:,} records")

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
            total_raw_rows = 0
            total_cleaned_rows = 0
            total_inserted = 0
            chunk_num = 0

            # Read CSV in chunks
            logger.info(f"Reading CSV file in chunks of {self.read_chunk_size:,}...")
            csv_chunks = pd.read_csv(
                file_path,
                sep='|',
                encoding='utf-8',
                low_memory=False,
                chunksize=self.read_chunk_size
            )

            for chunk in csv_chunks:
                chunk_num += 1
                total_raw_rows += len(chunk)

                logger.info(f"Processing chunk {chunk_num} ({len(chunk):,} raw rows, {total_raw_rows:,} total raw)")

                # Clean the chunk
                cleaned_chunk = self.clean_chunk(chunk, data_year)
                total_cleaned_rows += len(cleaned_chunk)

                logger.info(f"  Cleaned to {len(cleaned_chunk):,} rows ({total_cleaned_rows:,} total cleaned)")

                # Write cleaned chunk in smaller batches
                for i in range(0, len(cleaned_chunk), self.write_batch_size):
                    batch = cleaned_chunk.iloc[i:i + self.write_batch_size]

                    stats = self.upsert_batch(batch, source_file, file_hash)
                    total_inserted += stats['inserted']

                    self.db.commit()

                logger.info(f"  Chunk {chunk_num} completed - Total inserted: {total_inserted:,}")

            # Update import record
            import_record.total_records = total_cleaned_rows
            import_record.inserted_records = total_inserted
            import_record.updated_records = 0
            import_record.skipped_records = total_cleaned_rows - total_inserted
            import_record.completed_at = datetime.utcnow()
            import_record.duration_seconds = (import_record.completed_at - import_record.started_at).total_seconds()
            import_record.status = 'completed'

            self.db.commit()

            logger.info(f"✓ Import completed successfully!")
            logger.info(f"  Raw records read: {total_raw_rows:,}")
            logger.info(f"  Cleaned records: {total_cleaned_rows:,}")
            logger.info(f"  Inserted: {import_record.inserted_records:,}")
            logger.info(f"  Skipped: {import_record.skipped_records:,}")
            logger.info(f"  Duration: {import_record.duration_seconds:.1f}s")
            logger.info(f"  Throughput: {total_cleaned_rows / import_record.duration_seconds:.0f} records/sec")

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
    parser = argparse.ArgumentParser(description='Import DVF data with chunked reading')
    parser.add_argument('file_path', help='Path to DVF CSV file')
    parser.add_argument('--year', type=int, required=True, help='Data year (e.g., 2023)')
    parser.add_argument('--force', action='store_true', help='Force re-import even if file hash exists')
    parser.add_argument('--read-chunk-size', type=int, default=50000, help='CSV read chunk size')
    parser.add_argument('--write-batch-size', type=int, default=10000, help='DB write batch size')

    args = parser.parse_args()

    # Validate file exists
    if not os.path.exists(args.file_path):
        logger.error(f"File not found: {args.file_path}")
        sys.exit(1)

    # Import
    db = SessionLocal()
    try:
        importer = ChunkedDVFImporter(
            db,
            read_chunk_size=args.read_chunk_size,
            write_batch_size=args.write_batch_size
        )
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
