"""
Rollback a specific DVF import batch.

Usage:
    python scripts/rollback_dvf_import.py <batch_id>

Example:
    python scripts/rollback_dvf_import.py a1b2c3d4-e5f6-7890-abcd-ef1234567890
"""

import sys
import os
import argparse
import logging

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


def rollback_import(batch_id: str):
    """Rollback a specific import batch."""

    db = SessionLocal()
    try:
        # Get import record
        import_record = db.query(DVFImport).filter(
            DVFImport.batch_id == batch_id
        ).first()

        if not import_record:
            logger.error(f"Import batch not found: {batch_id}")
            sys.exit(1)

        logger.info(f"Found import: {import_record.source_file}")
        logger.info(f"Status: {import_record.status}")
        logger.info(f"Imported: {import_record.inserted_records:,} records")

        # Confirm rollback
        response = input(f"\nRollback this import? This will DELETE {import_record.inserted_records:,} records. (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Rollback cancelled")
            return

        # Delete records from this batch
        logger.info(f"Deleting records with import_batch_id = {batch_id}...")

        deleted_count = db.query(DVFRecord).filter(
            DVFRecord.import_batch_id == batch_id
        ).delete(synchronize_session=False)

        # Update import record status
        import_record.status = 'rolled_back'

        db.commit()

        logger.info(f"✓ Rolled back {deleted_count:,} records from batch {batch_id}")
        logger.info(f"Import record marked as 'rolled_back'")

    except Exception as e:
        db.rollback()
        logger.error(f"Rollback failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


def list_imports():
    """List all import batches."""

    db = SessionLocal()
    try:
        imports = db.query(DVFImport).order_by(DVFImport.started_at.desc()).all()

        if not imports:
            logger.info("No imports found")
            return

        logger.info(f"\nFound {len(imports)} import(s):\n")

        for imp in imports:
            logger.info(f"Batch ID: {imp.batch_id}")
            logger.info(f"  File: {imp.source_file}")
            logger.info(f"  Year: {imp.data_year}")
            logger.info(f"  Status: {imp.status}")
            logger.info(f"  Records: {imp.inserted_records:,}")
            logger.info(f"  Started: {imp.started_at}")
            logger.info("")

    finally:
        db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Rollback DVF import batch')
    parser.add_argument('batch_id', nargs='?', help='Batch ID to rollback')
    parser.add_argument('--list', action='store_true', help='List all import batches')

    args = parser.parse_args()

    if args.list:
        list_imports()
    elif args.batch_id:
        rollback_import(args.batch_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
