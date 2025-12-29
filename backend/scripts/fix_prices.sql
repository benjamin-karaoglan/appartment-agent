-- Fix prices that are 100x too high due to incorrect comma handling
-- The issue: French format uses comma as decimal separator (1268540,00 = 1,268,540.00)
-- Our import removed the comma instead of converting it to decimal point

BEGIN;

-- First, verify the issue
SELECT
    'BEFORE FIX - Sample prices:' as status,
    MIN(sale_price) as min_price,
    MAX(sale_price) as max_price,
    ROUND(AVG(sale_price)::numeric, 2) as avg_price
FROM dvf_records;

-- Fix: Divide all prices by 100 to correct the error
UPDATE dvf_records
SET
    sale_price = sale_price / 100,
    price_per_sqm = CASE
        WHEN price_per_sqm IS NOT NULL THEN price_per_sqm / 100
        ELSE NULL
    END;

-- Verify the fix
SELECT
    'AFTER FIX - Sample prices:' as status,
    MIN(sale_price) as min_price,
    MAX(sale_price) as max_price,
    ROUND(AVG(sale_price)::numeric, 2) as avg_price
FROM dvf_records;

COMMIT;

-- Show sample of fixed prices
SELECT
    sale_date,
    TO_CHAR(sale_price, 'FM999,999,999.99') || ' €' as price,
    address,
    postal_code,
    surface_area,
    TO_CHAR(price_per_sqm, 'FM999,999.99') || ' €/m²' as price_sqm
FROM dvf_records
WHERE postal_code = '75006'
  AND address LIKE '%NOTRE-DAME DES CHAMPS%'
ORDER BY sale_date DESC
LIMIT 10;
