#!/bin/bash

# Script to reimport DVF data for 2023-2025
# This will clear existing data and reimport with the fixed import script

cd /Users/carrefour/appartment-agent/backend

echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "WARNING: This will delete all existing DVF records and reimport."
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

echo ""
echo "Deleting existing DVF records..."
python -c "
from app.core.database import SessionLocal
from app.models.property import DVFRecord

db = SessionLocal()
count = db.query(DVFRecord).count()
print(f'Current DVF records: {count:,}')
print('Deleting all records...')
db.query(DVFRecord).delete()
db.commit()
print('Done!')
db.close()
"

echo ""
echo "Importing 2023 data..."
python scripts/import_dvf.py /Users/carrefour/dvf/dvf/data/dvf/ValeursFoncieres-2023.txt

echo ""
echo "Importing 2024 data..."
python scripts/import_dvf.py /Users/carrefour/dvf/dvf/data/dvf/ValeursFoncieres-2024.txt

echo ""
echo "Importing 2025-S1 data..."
python scripts/import_dvf.py /Users/carrefour/dvf/dvf/data/dvf/ValeursFoncieres-2025-S1.txt

echo ""
echo "Verifying 56 RUE NOTRE-DAME DES CHAMPS records..."
python -c "
from app.core.database import SessionLocal
from app.models.property import DVFRecord

db = SessionLocal()

records = db.query(DVFRecord).filter(
    DVFRecord.address.like('56 RUE NOTRE-DAME DES CHAMPS%'),
    DVFRecord.postal_code == '75006'
).order_by(DVFRecord.sale_date.desc()).all()

print(f'\nFound {len(records)} records for 56 RUE NOTRE-DAME DES CHAMPS 75006:')
print()

db.close()
"

echo ""
echo "Import complete!"
