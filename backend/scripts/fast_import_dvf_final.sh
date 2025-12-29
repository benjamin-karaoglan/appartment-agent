#!/bin/bash
set -e

# FINAL VERSION: Fast DVF import with all fixes applied
# - Uses server-side COPY for maximum speed
# - Handles division by zero correctly
# - Imports all years (2021-2025)

echo "=================================================="
echo "DVF FAST BULK IMPORT - Final Version"
echo "=================================================="
echo ""

# Configuration
DB_CONTAINER="appartment-agent-db-1"
DB_NAME="appartment_agent"
DB_USER="appartment"
DATA_DIR="/Users/carrefour/appartment-agent/data/dvf"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Configuration:"
echo "  Database: $DB_NAME @ $DB_CONTAINER"
echo "  Data directory: $DATA_DIR"
echo ""

# Check container
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    echo "ERROR: Database container not running!"
    echo "Start with: docker-compose up -d"
    exit 1
fi
echo "✓ Database container running"
echo ""

# Confirmation
echo "WARNING: This will DELETE ALL existing DVF records!"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# Delete existing records
echo ""
echo "Step 1/6: Deleting existing records..."
echo "=========================================="
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$SCRIPT_DIR/delete_all_dvf.sql"
echo ""

# Import files
FILES=(
    "ValeursFoncieres-2021.txt:2021"
    "ValeursFoncieres-2022.txt:2022"
    "ValeursFoncieres-2023.txt:2023"
    "ValeursFoncieres-2024.txt:2024"
    "ValeursFoncieres-2025-S1.txt:2025"
)

STEP=2
TOTAL_START=$(date +%s)

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
        STEP=$((STEP + 1))
        continue
    fi

    echo "File: $FILEPATH"
    echo "Size: $(ls -lh "$FILEPATH" | awk '{print $5}')"
    echo "Lines: $(wc -l < "$FILEPATH" | tr -d ' ')"
    echo ""

    # Copy to container
    echo "Copying file to container..."
    docker cp "$FILEPATH" "$DB_CONTAINER:/tmp/$FILE"

    # Generate import SQL with NULLIF fix for division by zero
    cat > /tmp/import_${YEAR}.sql <<EOF
\timing on

BEGIN;

SET session_replication_role = 'replica';
SET synchronous_commit = OFF;
SET maintenance_work_mem = '512MB';
SET work_mem = '256MB';

DROP TABLE IF EXISTS dvf_staging;
CREATE UNLOGGED TABLE dvf_staging (
    identifiant_document text, reference_document text, articles_cgi_1 text, articles_cgi_2 text,
    articles_cgi_3 text, articles_cgi_4 text, articles_cgi_5 text, no_disposition text,
    date_mutation text, nature_mutation text, valeur_fonciere text, no_voie text, btq text,
    type_de_voie text, code_voie text, voie text, code_postal text, commune text,
    code_departement text, code_commune text, prefixe_de_section text, section text,
    no_plan text, no_volume text, lot_1 text, surface_carrez_1 text, lot_2 text,
    surface_carrez_2 text, lot_3 text, surface_carrez_3 text, lot_4 text,
    surface_carrez_4 text, lot_5 text, surface_carrez_5 text, nombre_de_lots text,
    code_type_local text, type_local text, identifiant_local text, surface_reelle_bati text,
    nombre_pieces_principales text, nature_culture text, nature_culture_speciale text,
    surface_terrain text
);

COPY dvf_staging FROM '/tmp/$FILE' WITH (FORMAT csv, DELIMITER '|', HEADER true, NULL '', ENCODING 'UTF8');

INSERT INTO dvf_records (
    sale_date, sale_price, address, postal_code, city, department,
    property_type, surface_area, rooms, land_surface, price_per_sqm,
    raw_data, data_year, source_file, import_batch_id, transaction_group_id, created_at
)
SELECT
    CASE WHEN date_mutation ~ '^\d{2}/\d{2}/\d{4}\$' THEN TO_DATE(date_mutation, 'DD/MM/YYYY') ELSE NULL END,
    CASE WHEN valeur_fonciere ~ '^[\d,]+\.?\d*\$' THEN REPLACE(valeur_fonciere, ',', '.')::numeric ELSE NULL END,
    TRIM(COALESCE(no_voie || ' ', '') || COALESCE(btq || ' ', '') || COALESCE(type_de_voie || ' ', '') || COALESCE(voie, '')),
    code_postal,
    commune,
    code_departement,
    type_local,
    CASE WHEN surface_reelle_bati ~ '^[\d,]+\.?\d*\$' THEN REPLACE(surface_reelle_bati, ',', '.')::numeric
         WHEN surface_carrez_1 ~ '^[\d,]+\.?\d*\$' THEN REPLACE(surface_carrez_1, ',', '.')::numeric
         ELSE NULL END,
    CASE WHEN nombre_pieces_principales ~ '^\d+\$' THEN nombre_pieces_principales::integer ELSE NULL END,
    CASE WHEN surface_terrain ~ '^[\d,]+\.?\d*\$' THEN REPLACE(surface_terrain, ',', '.')::numeric ELSE NULL END,
    -- FIXED: Use NULLIF to prevent division by zero, prioritize surface_reelle_bati
    CASE WHEN valeur_fonciere ~ '^[\d,]+\.?\d*\$' AND (surface_reelle_bati ~ '^[\d,]+\.?\d*\$' OR surface_carrez_1 ~ '^[\d,]+\.?\d*\$') THEN
        REPLACE(valeur_fonciere, ',', '.')::numeric / NULLIF(GREATEST(
            CASE WHEN surface_reelle_bati ~ '^[\d,]+\.?\d*\$' THEN REPLACE(surface_reelle_bati, ',', '.')::numeric ELSE 0 END,
            CASE WHEN surface_carrez_1 ~ '^[\d,]+\.?\d*\$' THEN REPLACE(surface_carrez_1, ',', '.')::numeric ELSE 0 END
        ), 0)
    ELSE NULL END,
    json_build_object('identifiant_document', identifiant_document, 'nature_mutation', nature_mutation, 'nombre_de_lots', nombre_de_lots, 'code_type_local', code_type_local)::text,
    $YEAR,
    '/tmp/$FILE',
    gen_random_uuid()::text,
    MD5(COALESCE(date_mutation, '') || COALESCE(valeur_fonciere, '') || COALESCE(code_postal, '') || COALESCE(voie, '')),
    NOW()
FROM dvf_staging
WHERE date_mutation ~ '^\d{2}/\d{2}/\d{4}\$'
  AND valeur_fonciere ~ '^[\d,]+\.?\d*\$'
  AND REPLACE(valeur_fonciere, ',', '.')::numeric > 0
  AND type_local IN ('Appartement', 'Maison')
  AND code_postal IS NOT NULL AND code_postal != ''
ON CONFLICT (sale_date, sale_price, address, postal_code, surface_area) DO NOTHING;

SELECT 'Year $YEAR: ' || COUNT(*)::text || ' records inserted' FROM dvf_records WHERE data_year = $YEAR;

DROP TABLE dvf_staging;
SET session_replication_role = 'origin';

COMMIT;
ANALYZE dvf_records;
EOF

    # Execute
    echo "Importing..."
    START=$(date +%s)
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < /tmp/import_${YEAR}.sql 2>&1 | grep -v "^NOTICE:"
    END=$(date +%s)
    DURATION=$((END - START))

    # Cleanup
    docker exec "$DB_CONTAINER" rm -f "/tmp/$FILE"
    rm -f /tmp/import_${YEAR}.sql

    echo ""
    echo "✓ Completed in $DURATION seconds"

    STEP=$((STEP + 1))
done

TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))

# Final statistics
echo ""
echo "=================================================="
echo "IMPORT COMPLETE!"
echo "=================================================="
echo "Total time: $TOTAL_DURATION seconds (~$((TOTAL_DURATION / 60)) minutes)"
echo ""

docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" <<'SQL'
SELECT
    data_year,
    TO_CHAR(COUNT(*), '999,999,999') as record_count,
    TO_CHAR(COUNT(*) FILTER (WHERE property_type = 'Appartement'), '999,999,999') as appartements,
    TO_CHAR(COUNT(*) FILTER (WHERE property_type = 'Maison'), '999,999,999') as maisons,
    MIN(sale_date) as earliest_sale,
    MAX(sale_date) as latest_sale
FROM dvf_records
GROUP BY data_year
ORDER BY data_year;

SELECT
    TO_CHAR(COUNT(*), '999,999,999') as total_records,
    ROUND((pg_total_relation_size('dvf_records')::numeric / 1024 / 1024), 2) || ' MB' as database_size
FROM dvf_records;
SQL

echo ""
echo "Refreshing grouped transactions view..."
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
REFRESH MATERIALIZED VIEW CONCURRENTLY dvf_grouped_transactions;
SELECT 'GROUPED TRANSACTIONS: ' || TO_CHAR(COUNT(*), '999,999,999') FROM dvf_grouped_transactions;
"

echo ""
echo "✓ All imports completed successfully!"
echo ""
