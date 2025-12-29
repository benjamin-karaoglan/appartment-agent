#!/bin/bash
set -e  # Exit on error

# Fast DVF import using PostgreSQL COPY
# This is 100-1000x faster than Python row-by-row inserts

echo "=================================================="
echo "FAST DVF BULK IMPORT (PostgreSQL COPY)"
echo "=================================================="
echo ""

# Database connection details
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="appartment_agent"
DB_USER="appartment"
DB_PASSWORD="appartment"

# PostgreSQL connection string
export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"

# Data directory (adjust if needed)
DATA_DIR="/Users/carrefour/appartment-agent/data/dvf"

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Configuration:"
echo "  Database: $DB_NAME @ $DB_HOST:$DB_PORT"
echo "  User: $DB_USER"
echo "  Data directory: $DATA_DIR"
echo ""

# Check if database is accessible
echo "Testing database connection..."
if ! $PSQL -c "SELECT 1;" > /dev/null 2>&1; then
    echo "ERROR: Cannot connect to database!"
    echo "Please ensure Docker is running: docker-compose up -d"
    exit 1
fi
echo "✓ Database connection OK"
echo ""

# Confirmation prompt
echo "WARNING: This will DELETE ALL existing DVF records!"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# Step 1: Delete all existing records
echo ""
echo "Step 1/6: Deleting all existing DVF records..."
echo "=========================================="
$PSQL -f "$SCRIPT_DIR/delete_all_dvf.sql"
echo ""

# Step 2-6: Import each year
FILES=(
    "ValeursFoncieres-2021.txt:2021"
    "ValeursFoncieres-2022.txt:2022"
    "ValeursFoncieres-2023.txt:2023"
    "ValeursFoncieres-2024.txt:2024"
    "ValeursFoncieres-2025-S1.txt:2025"
)

STEP=2
for FILE_YEAR in "${FILES[@]}"; do
    FILE="${FILE_YEAR%%:*}"
    YEAR="${FILE_YEAR##*:}"
    FILEPATH="$DATA_DIR/$FILE"

    echo ""
    echo "Step $STEP/6: Importing $FILE (year $YEAR)..."
    echo "=========================================="

    if [ ! -f "$FILEPATH" ]; then
        echo "WARNING: File not found: $FILEPATH"
        echo "Skipping..."
    else
        echo "File: $FILEPATH"
        echo "Size: $(ls -lh "$FILEPATH" | awk '{print $5}')"
        echo "Lines: $(wc -l < "$FILEPATH" | tr -d ' ')"
        echo ""
        echo "Starting import..."

        # Run the import with timing
        START_TIME=$(date +%s)

        $PSQL \
            -v filepath="$FILEPATH" \
            -v year="$YEAR" \
            -f "$SCRIPT_DIR/bulk_import_dvf.sql"

        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))

        echo ""
        echo "✓ Import completed in $DURATION seconds"
    fi

    STEP=$((STEP + 1))
done

# Final statistics
echo ""
echo "=================================================="
echo "IMPORT COMPLETE! Final Statistics:"
echo "=================================================="

$PSQL -c "
SELECT
    data_year,
    COUNT(*) as record_count,
    COUNT(*) FILTER (WHERE property_type = 'Appartement') as appartements,
    COUNT(*) FILTER (WHERE property_type = 'Maison') as maisons,
    MIN(sale_date) as earliest_sale,
    MAX(sale_date) as latest_sale,
    ROUND(AVG(sale_price)::numeric, 2) as avg_price,
    ROUND(AVG(price_per_sqm)::numeric, 2) as avg_price_per_sqm
FROM dvf_records
GROUP BY data_year
ORDER BY data_year;

SELECT
    'TOTAL RECORDS: ' || COUNT(*)::text as summary
FROM dvf_records;
"

echo ""
echo "✓ All imports completed successfully!"
echo ""
