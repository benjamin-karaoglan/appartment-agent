-- Create a materialized view for grouped DVF transactions
-- This aggregates multi-unit sales (same transaction_group_id) into single records

-- Drop existing view if exists
DROP MATERIALIZED VIEW IF EXISTS dvf_grouped_transactions CASCADE;

-- Create materialized view that groups multi-unit sales
CREATE MATERIALIZED VIEW dvf_grouped_transactions AS
SELECT
    -- Use MIN(id) as the representative ID for this transaction group
    MIN(id) as id,

    -- Transaction info (same for all lots in the group)
    transaction_group_id,
    sale_date,
    MAX(sale_price) as sale_price,  -- All lots have same price, use MAX for consistency

    -- Address info (same for all lots)
    MAX(address) as address,
    MAX(postal_code) as postal_code,
    MAX(city) as city,
    MAX(department) as department,
    MAX(property_type) as property_type,

    -- Aggregated surface info (SUM across all lots)
    SUM(surface_area) as total_surface_area,
    SUM(COALESCE(land_surface, 0)) as total_land_surface,

    -- Aggregated room count (SUM across all lots)
    SUM(COALESCE(rooms, 0)) as total_rooms,

    -- Count of units in this transaction
    COUNT(*) as unit_count,

    -- Calculated price per sqm for the ENTIRE transaction
    CASE
        WHEN SUM(surface_area) > 0 THEN
            MAX(sale_price) / SUM(surface_area)
        ELSE NULL
    END as grouped_price_per_sqm,

    -- Metadata
    MAX(data_year) as data_year,
    MAX(source_file) as source_file,
    MAX(import_batch_id) as import_batch_id,
    MIN(created_at) as created_at,

    -- Array of individual lot details for drill-down
    json_agg(
        json_build_object(
            'id', id,
            'surface_area', surface_area,
            'rooms', rooms,
            'price_per_sqm', price_per_sqm,
            'land_surface', land_surface
        ) ORDER BY surface_area DESC
    ) as lots_detail

FROM dvf_records
WHERE transaction_group_id IS NOT NULL
GROUP BY transaction_group_id, sale_date;

-- Add indexes for performance
CREATE INDEX idx_dvf_grouped_postal ON dvf_grouped_transactions(postal_code);
CREATE INDEX idx_dvf_grouped_date ON dvf_grouped_transactions(sale_date);
CREATE INDEX idx_dvf_grouped_type ON dvf_grouped_transactions(property_type);
CREATE INDEX idx_dvf_grouped_address ON dvf_grouped_transactions USING gin(address gin_trgm_ops);
CREATE UNIQUE INDEX idx_dvf_grouped_tx_id ON dvf_grouped_transactions(transaction_group_id);

-- Analyze for query optimization
ANALYZE dvf_grouped_transactions;

-- Create a function to refresh the view
CREATE OR REPLACE FUNCTION refresh_dvf_grouped_transactions()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dvf_grouped_transactions;
END;
$$ LANGUAGE plpgsql;

COMMENT ON MATERIALIZED VIEW dvf_grouped_transactions IS
'Grouped DVF transactions that aggregates multi-unit sales (same transaction_group_id) into single records.
Each row represents ONE real estate transaction, even if it involved multiple lots/units.';
