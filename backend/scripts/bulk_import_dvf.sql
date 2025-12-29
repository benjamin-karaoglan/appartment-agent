-- Fast bulk import of DVF data using PostgreSQL COPY
-- This script is designed to be run multiple times for different files
-- Usage: psql <connection> -v filepath='/path/to/file.txt' -v year=2023 -f bulk_import_dvf.sql

\timing on
\set VERBOSITY verbose

-- Parameters (set via -v flag):
-- :filepath - full path to DVF file
-- :year - year of the data (2021, 2022, etc.)

BEGIN;

-- Disable triggers and constraints for maximum speed
SET session_replication_role = 'replica';
SET synchronous_commit = OFF;
SET maintenance_work_mem = '512MB';
SET work_mem = '256MB';

-- Create temporary staging table (UNLOGGED for speed - no WAL overhead)
DROP TABLE IF EXISTS dvf_staging;
CREATE UNLOGGED TABLE dvf_staging (
    -- All columns from the DVF file (pipe-delimited)
    identifiant_document text,
    reference_document text,
    articles_cgi_1 text,
    articles_cgi_2 text,
    articles_cgi_3 text,
    articles_cgi_4 text,
    articles_cgi_5 text,
    no_disposition text,
    date_mutation text,
    nature_mutation text,
    valeur_fonciere text,
    no_voie text,
    btq text,
    type_de_voie text,
    code_voie text,
    voie text,
    code_postal text,
    commune text,
    code_departement text,
    code_commune text,
    prefixe_de_section text,
    section text,
    no_plan text,
    no_volume text,
    lot_1 text,
    surface_carrez_1 text,
    lot_2 text,
    surface_carrez_2 text,
    lot_3 text,
    surface_carrez_3 text,
    lot_4 text,
    surface_carrez_4 text,
    lot_5 text,
    surface_carrez_5 text,
    nombre_de_lots text,
    code_type_local text,
    type_local text,
    identifiant_local text,
    surface_reelle_bati text,
    nombre_pieces_principales text,
    nature_culture text,
    nature_culture_speciale text,
    surface_terrain text
);

-- Load data using COPY (fastest method)
\echo ''
\echo 'Loading data from file: ' :filepath
\echo 'Data year: ' :year
\echo ''

\copy dvf_staging FROM :filepath WITH (FORMAT csv, DELIMITER '|', HEADER true, NULL '', ENCODING 'UTF8')

\echo ''
\echo 'Data loaded into staging table. Processing...'
\echo ''

-- Transform and insert into dvf_records
INSERT INTO dvf_records (
    sale_date,
    sale_price,
    address,
    postal_code,
    city,
    department,
    property_type,
    surface_area,
    rooms,
    land_surface,
    price_per_sqm,
    raw_data,
    data_year,
    source_file,
    import_batch_id,
    transaction_group_id,
    created_at
)
SELECT
    -- Parse date (DD/MM/YYYY format)
    CASE
        WHEN date_mutation ~ '^\d{2}/\d{2}/\d{4}$' THEN
            TO_DATE(date_mutation, 'DD/MM/YYYY')
        ELSE NULL
    END as sale_date,

    -- Parse price (remove commas, convert to float)
    CASE
        WHEN valeur_fonciere ~ '^[\d,]+\.?\d*$' THEN
            REPLACE(valeur_fonciere, ',', '')::numeric
        ELSE NULL
    END as sale_price,

    -- Build address
    TRIM(COALESCE(no_voie || ' ', '') || COALESCE(btq || ' ', '') ||
         COALESCE(type_de_voie || ' ', '') || COALESCE(voie, '')) as address,

    -- Postal code
    code_postal,

    -- City
    commune as city,

    -- Department
    code_departement as department,

    -- Property type
    type_local as property_type,

    -- Surface area (use Carrez surface if available, otherwise built surface)
    CASE
        WHEN surface_carrez_1 ~ '^[\d,]+\.?\d*$' THEN
            REPLACE(surface_carrez_1, ',', '.')::numeric
        WHEN surface_reelle_bati ~ '^[\d,]+\.?\d*$' THEN
            REPLACE(surface_reelle_bati, ',', '.')::numeric
        ELSE NULL
    END as surface_area,

    -- Number of rooms
    CASE
        WHEN nombre_pieces_principales ~ '^\d+$' THEN
            nombre_pieces_principales::integer
        ELSE NULL
    END as rooms,

    -- Land surface
    CASE
        WHEN surface_terrain ~ '^[\d,]+\.?\d*$' THEN
            REPLACE(surface_terrain, ',', '.')::numeric
        ELSE NULL
    END as land_surface,

    -- Calculate price per sqm
    CASE
        WHEN valeur_fonciere ~ '^[\d,]+\.?\d*$' AND
             (surface_carrez_1 ~ '^[\d,]+\.?\d*$' OR surface_reelle_bati ~ '^[\d,]+\.?\d*$') THEN
            REPLACE(valeur_fonciere, ',', '')::numeric /
            GREATEST(
                CASE WHEN surface_carrez_1 ~ '^[\d,]+\.?\d*$' THEN REPLACE(surface_carrez_1, ',', '.')::numeric ELSE 0 END,
                CASE WHEN surface_reelle_bati ~ '^[\d,]+\.?\d*$' THEN REPLACE(surface_reelle_bati, ',', '.')::numeric ELSE 0 END
            )
        ELSE NULL
    END as price_per_sqm,

    -- Store raw data as JSON for reference
    json_build_object(
        'identifiant_document', identifiant_document,
        'nature_mutation', nature_mutation,
        'nombre_de_lots', nombre_de_lots,
        'code_type_local', code_type_local
    )::text as raw_data,

    -- Data year (from parameter)
    :year::integer as data_year,

    -- Source file
    :filepath as source_file,

    -- Import batch ID (generated UUID)
    gen_random_uuid()::text as import_batch_id,

    -- Transaction group ID (hash of sale date + price + address + postal)
    MD5(COALESCE(date_mutation, '') || COALESCE(valeur_fonciere, '') ||
        COALESCE(code_postal, '') || COALESCE(voie, '')) as transaction_group_id,

    -- Import timestamp
    NOW() as created_at

FROM dvf_staging
WHERE
    -- Filter: only valid dates
    date_mutation ~ '^\d{2}/\d{2}/\d{4}$'
    -- Filter: only records with prices
    AND valeur_fonciere ~ '^[\d,]+\.?\d*$'
    AND REPLACE(valeur_fonciere, ',', '')::numeric > 0
    -- Filter: only Appartements and Maisons
    AND type_local IN ('Appartement', 'Maison')
    -- Filter: postal code exists
    AND code_postal IS NOT NULL AND code_postal != ''

-- Handle duplicates using ON CONFLICT (upsert)
ON CONFLICT ON CONSTRAINT idx_dvf_unique_sale DO NOTHING;

-- Get statistics
SELECT
    'Records loaded into staging: ' || COUNT(*)::text
FROM dvf_staging;

SELECT
    'Records inserted into dvf_records: ' || COUNT(*)::text
FROM dvf_records
WHERE data_year = :year;

-- Cleanup
DROP TABLE dvf_staging;

-- Re-enable triggers
SET session_replication_role = 'origin';

COMMIT;

-- Analyze table for better query performance
ANALYZE dvf_records;

\echo ''
\echo 'Import completed successfully!'
\echo ''
