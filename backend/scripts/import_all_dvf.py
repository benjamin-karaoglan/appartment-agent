#!/usr/bin/env python3
"""
Automatic DVF importer - Imports all DVF files from data/dvf directory.
Designed to be run automatically on database initialization.

This script:
- Scans data/dvf/ for all .txt files
- Extracts year from filename (ValeursFoncieres-YYYY.txt or ValeursFoncieres-YYYY-S1.txt)
- Imports each file using chunked processing
- Tracks imports to avoid duplicates (using file hash)
- Can be safely re-run (idempotent)
"""

import sys
import os
from pathlib import Path
import re
import logging
import hashlib
import uuid
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, engine
from app.models.property import DVFRecord, DVFImport

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AllDVFImporter:
    """Automatic importer for all DVF files."""

    def __init__(self, dvf_dir: str = "/app/data/dvf"):
        self.dvf_dir = Path(dvf_dir)
        self.read_chunk_size = 50000  # Read CSV in chunks
        self.write_batch_size = 10000  # Write to DB in batches

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def extract_year_from_filename(self, filename: str) -> Optional[int]:
        """
        Extract year from DVF filename.

        Examples:
            ValeursFoncieres-2024.txt -> 2024
            ValeursFoncieres-2025-S1.txt -> 2025
        """
        match = re.search(r'ValeursFoncieres-(\d{4})', filename)
        if match:
            return int(match.group(1))
        return None

    def find_dvf_files(self) -> List[Dict[str, any]]:
        """Find all DVF .txt files in the data directory."""
        if not self.dvf_dir.exists():
            logger.warning(f"DVF directory not found: {self.dvf_dir}")
            return []

        files = []
        for file_path in sorted(self.dvf_dir.glob("*.txt")):
            year = self.extract_year_from_filename(file_path.name)
            if year:
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                files.append({
                    "path": file_path,
                    "filename": file_path.name,
                    "year": year,
                    "size_mb": file_size_mb
                })
                logger.info(f"Found: {file_path.name} ({file_size_mb:.1f} MB) - Year: {year}")
            else:
                logger.warning(f"Could not extract year from filename: {file_path.name}")

        return files

    def check_already_imported(self, db: Session, file_hash: str) -> bool:
        """Check if this file was already imported."""
        existing = db.query(DVFImport).filter(
            DVFImport.source_file_hash == file_hash,
            DVFImport.status == "completed"
        ).first()
        return existing is not None

    def import_file(self, db: Session, file_info: Dict) -> bool:
        """Import a single DVF file."""
        file_path = file_info["path"]
        year = file_info["year"]
        filename = file_info["filename"]

        logger.info(f"=" * 80)
        logger.info(f"Importing {filename} (Year: {year})")
        logger.info(f"=" * 80)

        # Calculate file hash
        logger.info("Calculating file hash...")
        file_hash = self.calculate_file_hash(file_path)
        logger.info(f"File hash: {file_hash}")

        # Check if already imported
        if self.check_already_imported(db, file_hash):
            logger.info(f"✓ File already imported, skipping: {filename}")
            return True

        # Create import record
        batch_id = str(uuid.uuid4())
        import_record = DVFImport(
            batch_id=batch_id,
            source_file=str(file_path),
            source_file_hash=file_hash,
            data_year=year,
            status="in_progress",
            started_at=datetime.utcnow()
        )
        db.add(import_record)
        db.commit()

        started_at = datetime.utcnow()
        total_records = 0
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        try:
            # Process file in chunks
            logger.info(f"Reading CSV in chunks of {self.read_chunk_size:,} rows...")

            chunk_num = 0
            for chunk_df in pd.read_csv(
                file_path,
                sep='|',
                dtype=str,
                chunksize=self.read_chunk_size,
                low_memory=False
            ):
                chunk_num += 1
                chunk_size = len(chunk_df)
                total_records += chunk_size

                logger.info(f"Processing chunk {chunk_num} ({chunk_size:,} rows, {total_records:,} total so far)")

                # Process chunk in batches
                for batch_start in range(0, chunk_size, self.write_batch_size):
                    batch_end = min(batch_start + self.write_batch_size, chunk_size)
                    batch_df = chunk_df.iloc[batch_start:batch_end]

                    batch_result = self._process_batch(db, batch_df, year, filename, file_hash, batch_id)
                    inserted += batch_result["inserted"]
                    updated += batch_result["updated"]
                    skipped += batch_result["skipped"]
                    errors += batch_result["errors"]

                    # Commit after each batch
                    db.commit()

                    if (batch_start + self.write_batch_size) % 50000 == 0:
                        logger.info(
                            f"  Progress: {total_records:,} read, "
                            f"{inserted:,} inserted, {updated:,} updated, "
                            f"{skipped:,} skipped, {errors:,} errors"
                        )

            # Update import record as completed
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            import_record.status = "completed"
            import_record.completed_at = completed_at
            import_record.duration_seconds = duration
            import_record.total_records = total_records
            import_record.inserted_records = inserted
            import_record.updated_records = updated
            import_record.skipped_records = skipped
            import_record.error_records = errors
            db.commit()

            logger.info(f"=" * 80)
            logger.info(f"✓ Import completed: {filename}")
            logger.info(f"  Duration: {duration:.1f}s ({total_records/duration:.0f} records/sec)")
            logger.info(f"  Total: {total_records:,} | Inserted: {inserted:,} | Updated: {updated:,}")
            logger.info(f"  Skipped: {skipped:,} | Errors: {errors:,}")
            logger.info(f"=" * 80)

            return True

        except Exception as e:
            logger.error(f"Error importing {filename}: {e}", exc_info=True)

            # Update import record as failed
            import_record.status = "failed"
            import_record.completed_at = datetime.utcnow()
            import_record.error_message = str(e)
            import_record.total_records = total_records
            import_record.inserted_records = inserted
            import_record.updated_records = updated
            import_record.skipped_records = skipped
            import_record.error_records = errors
            db.commit()

            return False

    def _process_batch(
        self,
        db: Session,
        batch_df: pd.DataFrame,
        year: int,
        filename: str,
        file_hash: str,
        batch_id: str
    ) -> Dict[str, int]:
        """Process a batch of records using UPSERT."""
        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        # Prepare batch data
        records = []
        for _, row in batch_df.iterrows():
            try:
                # Parse date
                sale_date = None
                if pd.notna(row.get('Date mutation')):
                    try:
                        sale_date = pd.to_datetime(row['Date mutation'], format='%d/%m/%Y').date()
                    except:
                        pass

                # Parse numeric fields
                def safe_float(val):
                    try:
                        return float(val) if pd.notna(val) and val != '' else None
                    except:
                        return None

                def safe_int(val):
                    try:
                        return int(float(val)) if pd.notna(val) and val != '' else None
                    except:
                        return None

                sale_price = safe_float(row.get('Valeur fonciere'))
                surface_area = safe_float(row.get('Surface reelle bati'))
                rooms = safe_int(row.get('Nombre pieces principales'))
                land_surface = safe_float(row.get('Surface terrain'))

                # Calculate price per sqm
                price_per_sqm = None
                if sale_price and surface_area and surface_area > 0:
                    price_per_sqm = sale_price / surface_area

                # Build address
                address_parts = []
                if pd.notna(row.get('Adresse numero')):
                    address_parts.append(str(row['Adresse numero']))
                if pd.notna(row.get('Adresse nom voie')):
                    address_parts.append(str(row['Adresse nom voie']))
                address = ' '.join(address_parts) if address_parts else None

                # Create transaction group ID for deduplication
                transaction_group_id = hashlib.md5(
                    f"{sale_date}_{sale_price}_{address}_{row.get('Code postal', '')}".encode()
                ).hexdigest()

                records.append({
                    'sale_date': sale_date,
                    'sale_price': sale_price,
                    'address': address,
                    'postal_code': row.get('Code postal'),
                    'city': row.get('Commune'),
                    'department': row.get('Code departement'),
                    'property_type': row.get('Type local'),
                    'surface_area': surface_area,
                    'rooms': rooms,
                    'land_surface': land_surface,
                    'price_per_sqm': price_per_sqm,
                    'raw_data': None,  # Skip raw data to save space
                    'data_year': year,
                    'source_file': filename,
                    'source_file_hash': file_hash,
                    'import_batch_id': batch_id,
                    'imported_at': datetime.utcnow(),
                    'transaction_group_id': transaction_group_id,
                    'created_at': datetime.utcnow()
                })

            except Exception as e:
                logger.debug(f"Error processing row: {e}")
                errors += 1

        if not records:
            return {"inserted": 0, "updated": 0, "skipped": 0, "errors": errors}

        # Use UPSERT (ON CONFLICT DO UPDATE)
        try:
            # Use raw SQL for efficient UPSERT
            insert_sql = text("""
                INSERT INTO dvf_records (
                    sale_date, sale_price, address, postal_code, city, department,
                    property_type, surface_area, rooms, land_surface, price_per_sqm,
                    raw_data, data_year, source_file, source_file_hash, import_batch_id,
                    imported_at, transaction_group_id, created_at
                ) VALUES (
                    :sale_date, :sale_price, :address, :postal_code, :city, :department,
                    :property_type, :surface_area, :rooms, :land_surface, :price_per_sqm,
                    :raw_data, :data_year, :source_file, :source_file_hash, :import_batch_id,
                    :imported_at, :transaction_group_id, :created_at
                )
                ON CONFLICT (sale_date, sale_price, address, postal_code, surface_area)
                DO UPDATE SET
                    import_batch_id = EXCLUDED.import_batch_id,
                    imported_at = EXCLUDED.imported_at,
                    source_file_hash = EXCLUDED.source_file_hash
                RETURNING (xmax = 0) AS inserted
            """)

            for record in records:
                result = db.execute(insert_sql, record)
                row = result.fetchone()
                if row and row[0]:  # xmax = 0 means INSERT
                    inserted += 1
                else:
                    updated += 1

        except Exception as e:
            logger.error(f"Batch insert error: {e}")
            errors += len(records)

        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "errors": errors
        }

    def import_all(self) -> bool:
        """Import all DVF files."""
        logger.info("=" * 80)
        logger.info("AUTOMATIC DVF IMPORT")
        logger.info("=" * 80)

        # Find all DVF files
        files = self.find_dvf_files()
        if not files:
            logger.warning("No DVF files found!")
            return False

        logger.info(f"\nFound {len(files)} DVF file(s) to import\n")

        # Import each file
        db = SessionLocal()
        try:
            success_count = 0
            for file_info in files:
                if self.import_file(db, file_info):
                    success_count += 1

            logger.info("\n" + "=" * 80)
            logger.info(f"ALL IMPORTS COMPLETE: {success_count}/{len(files)} successful")
            logger.info("=" * 80)

            return success_count == len(files)

        finally:
            db.close()


def main():
    """Main entry point."""
    importer = AllDVFImporter()
    success = importer.import_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
