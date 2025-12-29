-- DVF Data Quality Validation Script
-- Run this after import to check data quality
-- Usage: docker exec -i appartment-agent-db-1 psql -U appartment -d appartment_agent < validate_dvf_data.sql

\echo ''
\echo '=================================================='
\echo 'DVF DATA QUALITY VALIDATION REPORT'
\echo '=================================================='
\echo ''

-- 1. Overall Statistics
\echo '1. OVERALL STATISTICS'
\echo '===================='
SELECT
    'Total Records' as metric,
    TO_CHAR(COUNT(*), '999,999,999') as value
FROM dvf_records
UNION ALL
SELECT
    'Total Database Size',
    ROUND((pg_total_relation_size('dvf_records')::numeric / 1024 / 1024), 2) || ' MB'
FROM dvf_records
LIMIT 1;

\echo ''

-- 2. Records by Year
\echo '2. RECORDS BY YEAR'
\echo '=================='
SELECT
    data_year,
    TO_CHAR(COUNT(*), '999,999,999') as total_records,
    TO_CHAR(COUNT(*) FILTER (WHERE property_type = 'Appartement'), '999,999,999') as appartements,
    TO_CHAR(COUNT(*) FILTER (WHERE property_type = 'Maison'), '999,999,999') as maisons,
    MIN(sale_date) as earliest_sale,
    MAX(sale_date) as latest_sale
FROM dvf_records
GROUP BY data_year
ORDER BY data_year;

\echo ''

-- 3. Outlier Detection
\echo '3. OUTLIER DETECTION (Extreme Prices)'
\echo '======================================'
SELECT
    data_year,
    COUNT(*) FILTER (WHERE sale_price > 100000000) as "over_100M_€",
    COUNT(*) FILTER (WHERE sale_price < 10000) as "under_10K_€",
    COUNT(*) FILTER (WHERE price_per_sqm > 50000) as "price_sqm_over_50K",
    COUNT(*) FILTER (WHERE price_per_sqm < 100) as "price_sqm_under_100",
    COUNT(*) FILTER (WHERE price_per_sqm IS NULL) as "price_sqm_null"
FROM dvf_records
GROUP BY data_year
ORDER BY data_year;

\echo ''

-- 4. Missing Data Analysis
\echo '4. MISSING DATA ANALYSIS'
\echo '========================'
SELECT
    data_year,
    TO_CHAR(COUNT(*), '999,999,999') as total,
    TO_CHAR(COUNT(*) FILTER (WHERE surface_area IS NULL), '999,999,999') as missing_surface,
    ROUND(100.0 * COUNT(*) FILTER (WHERE surface_area IS NULL) / COUNT(*), 2) || '%' as pct_missing_surface,
    TO_CHAR(COUNT(*) FILTER (WHERE rooms IS NULL), '999,999,999') as missing_rooms,
    ROUND(100.0 * COUNT(*) FILTER (WHERE rooms IS NULL) / COUNT(*), 2) || '%' as pct_missing_rooms
FROM dvf_records
GROUP BY data_year
ORDER BY data_year;

\echo ''

-- 5. Address Quality
\echo '5. ADDRESS QUALITY'
\echo '=================='
SELECT
    'Empty or NULL addresses' as issue,
    COUNT(*) FILTER (WHERE address = '' OR address IS NULL) as count
FROM dvf_records
UNION ALL
SELECT
    'Suspiciously short addresses (<5 chars)',
    COUNT(*) FILTER (WHERE LENGTH(address) < 5)
FROM dvf_records
UNION ALL
SELECT
    'Missing city',
    COUNT(*) FILTER (WHERE city IS NULL OR city = '')
FROM dvf_records
UNION ALL
SELECT
    'Missing postal code',
    COUNT(*) FILTER (WHERE postal_code IS NULL OR postal_code = '')
FROM dvf_records;

\echo ''

-- 6. Price Distribution (Percentiles)
\echo '6. PRICE DISTRIBUTION - APPARTEMENTS (2024)'
\echo '============================================'
SELECT
    'P01 (1st percentile)' as percentile,
    TO_CHAR(PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY sale_price), 'FM999,999,999') || ' €' as price
FROM dvf_records
WHERE property_type = 'Appartement' AND data_year = 2024 AND sale_price IS NOT NULL
UNION ALL
SELECT 'P25 (25th percentile)', TO_CHAR(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY sale_price), 'FM999,999,999') || ' €'
FROM dvf_records WHERE property_type = 'Appartement' AND data_year = 2024 AND sale_price IS NOT NULL
UNION ALL
SELECT 'P50 (Median)', TO_CHAR(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY sale_price), 'FM999,999,999') || ' €'
FROM dvf_records WHERE property_type = 'Appartement' AND data_year = 2024 AND sale_price IS NOT NULL
UNION ALL
SELECT 'P75 (75th percentile)', TO_CHAR(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY sale_price), 'FM999,999,999') || ' €'
FROM dvf_records WHERE property_type = 'Appartement' AND data_year = 2024 AND sale_price IS NOT NULL
UNION ALL
SELECT 'P99 (99th percentile)', TO_CHAR(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY sale_price), 'FM999,999,999') || ' €'
FROM dvf_records WHERE property_type = 'Appartement' AND data_year = 2024 AND sale_price IS NOT NULL;

\echo ''

-- 7. Surface Area Distribution
\echo '7. SURFACE AREA DISTRIBUTION'
\echo '============================'
SELECT
    property_type,
    TO_CHAR(COUNT(*), '999,999,999') as total,
    ROUND(AVG(surface_area)::numeric, 2) as avg_surface_sqm,
    ROUND(STDDEV(surface_area)::numeric, 2) as stddev,
    ROUND(MIN(surface_area)::numeric, 2) as min_sqm,
    ROUND(MAX(surface_area)::numeric, 2) as max_sqm,
    COUNT(*) FILTER (WHERE surface_area < 10) as "under_10_sqm",
    COUNT(*) FILTER (WHERE surface_area > 500) as "over_500_sqm"
FROM dvf_records
WHERE surface_area IS NOT NULL
GROUP BY property_type;

\echo ''

-- 8. Top Departments by Sales
\echo '8. TOP 10 DEPARTMENTS BY SALES (2024)'
\echo '======================================'
SELECT
    department,
    TO_CHAR(COUNT(*), '999,999,999') as sales,
    COUNT(DISTINCT city) as num_cities,
    TO_CHAR(ROUND(AVG(price_per_sqm) FILTER (WHERE price_per_sqm > 0)::numeric, 2), 'FM999,999') || ' €/sqm' as avg_price_sqm
FROM dvf_records
WHERE data_year = 2024
GROUP BY department
ORDER BY COUNT(*) DESC
LIMIT 10;

\echo ''

-- 9. Price/Sqm for Major Cities
\echo '9. PRICE/SQM FOR PARIS ARRONDISSEMENTS (2024)'
\echo '=============================================='
SELECT
    city,
    postal_code,
    TO_CHAR(COUNT(*), '999,999') as sales,
    TO_CHAR(ROUND(AVG(price_per_sqm)::numeric, 2), 'FM999,999') || ' €' as avg_price_sqm,
    TO_CHAR(ROUND(MIN(price_per_sqm)::numeric, 2), 'FM999,999') || ' €' as min_price_sqm,
    TO_CHAR(ROUND(MAX(price_per_sqm)::numeric, 2), 'FM999,999') || ' €' as max_price_sqm
FROM dvf_records
WHERE price_per_sqm > 0
  AND data_year = 2024
  AND city LIKE 'PARIS%'
  AND property_type = 'Appartement'
GROUP BY city, postal_code
ORDER BY AVG(price_per_sqm) DESC
LIMIT 10;

\echo ''

-- 10. Potential Duplicates
\echo '10. POTENTIAL DUPLICATES (Same Date/Address, Different Prices)'
\echo '==============================================================='
SELECT
    address,
    postal_code,
    sale_date,
    COUNT(*) as occurrence_count,
    ARRAY_AGG(DISTINCT sale_price ORDER BY sale_price) as different_prices
FROM dvf_records
GROUP BY address, postal_code, sale_date
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 20;

\echo ''

-- 11. Data Completeness Score
\echo '11. DATA COMPLETENESS ANALYSIS'
\echo '==============================='
SELECT
    data_year,
    TO_CHAR(COUNT(*), '999,999,999') as total_records,
    ROUND(100.0 * COUNT(*) FILTER (
        WHERE sale_price IS NOT NULL
        AND surface_area IS NOT NULL
        AND address IS NOT NULL AND address != ''
        AND rooms IS NOT NULL
    ) / COUNT(*), 2) || '%' as pct_complete_records
FROM dvf_records
GROUP BY data_year
ORDER BY data_year;

\echo ''
\echo '=================================================='
\echo 'VALIDATION COMPLETE'
\echo '=================================================='
\echo ''
\echo 'Review the results above for any anomalies.'
\echo 'See DVF_IMPORT_GUIDE.md for detailed TODO actions.'
\echo ''
