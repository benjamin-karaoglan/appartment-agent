#!/bin/bash
set -e

echo "Importing 2021 data only..."

DB_CONTAINER="appartment-agent-db-1"
DB_NAME="appartment_agent"
DB_USER="appartment"
FILE="ValeursFoncieres-2021.txt"
DATA_DIR="/Users/carrefour/appartment-agent/data/dvf"

# Copy file
docker cp "$DATA_DIR/$FILE" "$DB_CONTAINER:/tmp/$FILE"

# Import with fixed division by zero handling
cat > /tmp/import_2021.sql <<'EOF'
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

COPY dvf_staging FROM '/tmp/ValeursFoncieres-2021.txt' WITH (FORMAT csv, DELIMITER '|', HEADER true, NULL '', ENCODING 'UTF8');

SELECT 'Loaded into staging: ' || COUNT(*)::text FROM dvf_staging;

INSERT INTO dvf_records (
    sale_date, sale_price, address, postal_code, city, department,
    property_type, surface_area, rooms, land_surface, price_per_sqm,
    raw_data, data_year, source_file, import_batch_id, transaction_group_id, created_at
)
SELECT
    CASE WHEN date_mutation ~ '^\d{2}/\d{2}/\d{4}$' THEN TO_DATE(date_mutation, 'DD/MM/YYYY') ELSE NULL END,
    CASE WHEN valeur_fonciere ~ '^[\d,]+\.?\d*$' THEN REPLACE(valeur_fonciere, ',', '')::numeric ELSE NULL END,
    TRIM(COALESCE(no_voie || ' ', '') || COALESCE(btq || ' ', '') || COALESCE(type_de_voie || ' ', '') || COALESCE(voie, '')),
    code_postal,
    commune,
    code_departement,
    type_local,
    CASE WHEN surface_carrez_1 ~ '^[\d,]+\.?\d*$' THEN REPLACE(surface_carrez_1, ',', '.')::numeric
         WHEN surface_reelle_bati ~ '^[\d,]+\.?\d*$' THEN REPLACE(surface_reelle_bati, ',', '.')::numeric
         ELSE NULL END,
    CASE WHEN nombre_pieces_principales ~ '^\d+$' THEN nombre_pieces_principales::integer ELSE NULL END,
    CASE WHEN surface_terrain ~ '^[\d,]+\.?\d*$' THEN REPLACE(surface_terrain, ',', '.')::numeric ELSE NULL END,
    -- Fixed division by zero with NULLIF
    CASE WHEN valeur_fonciere ~ '^[\d,]+\.?\d*$' AND (surface_carrez_1 ~ '^[\d,]+\.?\d*$' OR surface_reelle_bati ~ '^[\d,]+\.?\d*$') THEN
        REPLACE(valeur_fonciere, ',', '')::numeric / NULLIF(GREATEST(
            CASE WHEN surface_carrez_1 ~ '^[\d,]+\.?\d*$' THEN REPLACE(surface_carrez_1, ',', '.')::numeric ELSE 0 END,
            CASE WHEN surface_reelle_bati ~ '^[\d,]+\.?\d*$' THEN REPLACE(surface_reelle_bati, ',', '.')::numeric ELSE 0 END
        ), 0)
    ELSE NULL END,
    json_build_object('identifiant_document', identifiant_document, 'nature_mutation', nature_mutation, 'nombre_de_lots', nombre_de_lots, 'code_type_local', code_type_local)::text,
    2021,
    '/tmp/ValeursFoncieres-2021.txt',
    gen_random_uuid()::text,
    MD5(COALESCE(date_mutation, '') || COALESCE(valeur_fonciere, '') || COALESCE(code_postal, '') || COALESCE(voie, '')),
    NOW()
FROM dvf_staging
WHERE date_mutation ~ '^\d{2}/\d{2}/\d{4}$'
  AND valeur_fonciere ~ '^[\d,]+\.?\d*$'
  AND REPLACE(valeur_fonciere, ',', '')::numeric > 0
  AND type_local IN ('Appartement', 'Maison')
  AND code_postal IS NOT NULL AND code_postal != ''
ON CONFLICT (sale_date, sale_price, address, postal_code, surface_area) DO NOTHING;

SELECT 'Inserted records for 2021: ' || COUNT(*)::text FROM dvf_records WHERE data_year = 2021;

DROP TABLE dvf_staging;
SET session_replication_role = 'origin';

COMMIT;
ANALYZE dvf_records;

SELECT 'TOTAL RECORDS: ' || COUNT(*)::text FROM dvf_records;
EOF

START=$(date +%s)
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < /tmp/import_2021.sql
END=$(date +%s)

docker exec "$DB_CONTAINER" rm -f "/tmp/$FILE"
rm -f /tmp/import_2021.sql

echo ""
echo "✓ 2021 import completed in $((END - START)) seconds"
echo ""
