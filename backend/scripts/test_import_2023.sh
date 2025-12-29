#!/bin/bash
set -e

# Test import of just 2023 data to verify correctness

echo "=================================================="
echo "TEST DVF IMPORT - 2023 ONLY"
echo "=================================================="
echo ""

# Database connection details
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="appartment_agent"
DB_USER="appartment"
DB_PASSWORD="appartment"

export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"

DATA_DIR="/Users/carrefour/appartment-agent/data/dvf"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check database connection
echo "Testing database connection..."
if ! $PSQL -c "SELECT 1;" > /dev/null 2>&1; then
    echo "ERROR: Cannot connect to database!"
    exit 1
fi
echo "✓ Connected"
echo ""

# Delete existing records
echo "Deleting existing DVF records..."
$PSQL -f "$SCRIPT_DIR/delete_all_dvf.sql"
echo ""

# Import 2023 only
echo "Importing 2023 data..."
echo "=========================================="

$PSQL \
    -v filepath="$DATA_DIR/ValeursFoncieres-2023.txt" \
    -v year="2023" \
    -f "$SCRIPT_DIR/bulk_import_dvf.sql"

echo ""
echo "=================================================="
echo "Verification - Sample Records:"
echo "=================================================="

# Check sample records
$PSQL -c "
SELECT
    sale_date,
    sale_price,
    address,
    postal_code,
    city,
    property_type,
    surface_area,
    rooms,
    price_per_sqm
FROM dvf_records
WHERE postal_code = '75006'
ORDER BY sale_date DESC
LIMIT 10;
"

echo ""
echo "=================================================="
echo "Statistics:"
echo "=================================================="

$PSQL -c "
SELECT
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE property_type = 'Appartement') as appartements,
    COUNT(*) FILTER (WHERE property_type = 'Maison') as maisons,
    MIN(sale_date) as earliest_sale,
    MAX(sale_date) as latest_sale,
    ROUND(AVG(sale_price)::numeric, 2) as avg_price,
    ROUND(AVG(price_per_sqm) FILTER (WHERE price_per_sqm > 0)::numeric, 2) as avg_price_per_sqm
FROM dvf_records;
"

echo ""
echo "✓ Test import completed!"
echo ""
