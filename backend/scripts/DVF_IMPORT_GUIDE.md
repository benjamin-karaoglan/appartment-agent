# DVF Import Guide - Fast PostgreSQL COPY Method

## Overview

This directory contains scripts for **ultra-fast** bulk import of DVF (Demandes de Valeurs Foncières) data using PostgreSQL's native `COPY` command.

**Performance**: ~4.7 million records in ~7 minutes (100-1000x faster than Python row-by-row inserts)

---

## ⚠️ CRITICAL: French Number Format (FIXED)

**A critical bug was fixed on 2025-12-28**: Prices were 100x too high due to incorrect comma handling.

- **DVF format**: `1268540,00` (comma is **decimal separator**, not thousands!)
- **Fixed**: Now correctly converts to `1268540.00` euros
- **All import scripts updated** with correct parsing

See [PRICE_FIX_CHANGELOG.md](PRICE_FIX_CHANGELOG.md) for details.

---

## Files

### Import Scripts
- **[fast_import_dvf_final.sh](fast_import_dvf_final.sh)** - **RECOMMENDED**: Main import script with all fixes (2021-2025)
- **[fast_import_all_dvf_v2.sh](fast_import_all_dvf_v2.sh)** - Alternative import script
- **[test_import_2023_v2.sh](test_import_2023_v2.sh)** - Test script for single year import
- **[import_2021_only.sh](import_2021_only.sh)** - Import 2021 data separately (if needed)

### Utility Scripts
- **[delete_all_dvf.sql](delete_all_dvf.sql)** - Truncate all DVF records
- **[validate_dvf_data.sql](validate_dvf_data.sql)** - **NEW**: Comprehensive data quality validation report

## Quick Start

### 1. Ensure Docker is Running

```bash
docker-compose up -d
```

### 2. Run Full Import (All Years)

```bash
cd /Users/carrefour/appartment-agent/backend
./scripts/fast_import_all_dvf_v2.sh
```

This will:
1. Delete all existing DVF records
2. Import 2021-2025 data (5 files)
3. Show final statistics

**Total time**: ~7 minutes for 4.7 million records

### 3. Verify Import

Run the comprehensive validation report:

```bash
docker exec -i appartment-agent-db-1 psql -U appartment -d appartment_agent < scripts/validate_dvf_data.sql
```

Or quick check:

```bash
docker exec appartment-agent-db-1 psql -U appartment -d appartment_agent -c "
SELECT data_year, COUNT(*) FROM dvf_records GROUP BY data_year ORDER BY data_year;
"
```

## Performance Benchmarks

| Year | File Size | Lines      | Import Time | Records/sec |
|------|-----------|------------|-------------|-------------|
| 2021 | 599 MB    | 4,674,177  | 221s        | 5,847       |
| 2022 | 599 MB    | 4,675,008  | 109s        | 11,346      |
| 2023 | 485 MB    | 3,812,328  | 82s         | 11,700      |
| 2024 | 444 MB    | 3,489,150  | 118s        | 7,284       |
| 2025 | 176 MB    | 1,387,078  | 56s         | 6,289       |
| **TOTAL** | **2.3 GB** | **18M lines** | **~7 min** | **~11,000** |

## How It Works

### Key Optimizations

1. **Server-Side COPY**: Uses PostgreSQL's native `COPY FROM` command
   - Files copied into container at `/tmp/`
   - Direct server-side load (no client streaming overhead)

2. **UNLOGGED Staging Table**: No WAL overhead during initial load
   - Creates temporary `dvf_staging` table
   - Loads raw pipe-delimited data
   - Transforms and inserts into `dvf_records`

3. **Batch Processing**: Single transaction per file
   - Disables triggers: `SET session_replication_role = 'replica'`
   - Async commits: `SET synchronous_commit = OFF`
   - Large work memory: `512MB maintenance_work_mem`

4. **Deduplication**: `ON CONFLICT` clause handles duplicates
   - Uses unique index on `(sale_date, sale_price, address, postal_code, surface_area)`
   - Silently skips duplicates

5. **Post-Load Optimization**:
   - `ANALYZE` after each import
   - Rebuilds statistics for query planner

### Data Preprocessing & Transformation Pipeline

The import process includes comprehensive data cleaning and transformation:

#### 1. **Date Parsing & Validation**
```sql
CASE WHEN date_mutation ~ '^\d{2}/\d{2}/\d{4}$' THEN
    TO_DATE(date_mutation, 'DD/MM/YYYY')
ELSE NULL END
```
- Validates French date format (`DD/MM/YYYY`)
- Converts to PostgreSQL `DATE` type
- Rejects invalid dates (set to NULL)
- **Filter**: Only records with valid dates are imported

#### 2. **Price Parsing & Validation** ⚠️ CRITICAL
```sql
CASE WHEN valeur_fonciere ~ '^[\d,]+\.?\d*$' THEN
    REPLACE(valeur_fonciere, ',', '.')::numeric  -- CRITICAL: comma is decimal separator!
ELSE NULL END
```
- Validates numeric format with French decimal comma
- **Converts comma to decimal point** (`,` → `.`)
  - French format: `1268540,00` = **1,268,540.00 euros**
  - NOT a thousands separator!
- Converts to PostgreSQL `NUMERIC` type
- **Filter**: Only records with `price > 0` are imported
- ⚠️ **Bug fixed 2025-12-28**: Previous version incorrectly removed comma (100x price error)

#### 3. **Address Normalization**
```sql
TRIM(COALESCE(no_voie || ' ', '') ||
     COALESCE(btq || ' ', '') ||
     COALESCE(type_de_voie || ' ', '') ||
     COALESCE(voie, ''))
```
- Concatenates: street number + B/T/Q + street type + street name
- Handles NULL values with `COALESCE`
- Trims leading/trailing whitespace
- Example: `56` + `RUE` + `NOTRE-DAME DES CHAMPS` → `56 RUE NOTRE-DAME DES CHAMPS`

#### 4. **Surface Area Selection & Validation**
```sql
CASE
    WHEN surface_carrez_1 ~ '^[\d,]+\.?\d*$' THEN
        REPLACE(surface_carrez_1, ',', '.')::numeric
    WHEN surface_reelle_bati ~ '^[\d,]+\.?\d*$' THEN
        REPLACE(surface_reelle_bati, ',', '.')::numeric
    ELSE NULL
END
```
- **Priority 1**: Carrez surface (legal living space)
- **Priority 2**: Built surface (if Carrez unavailable)
- Converts French decimal format (`,` → `.`)
- Returns NULL if both unavailable

#### 5. **Price per Sqm Calculation**
```sql
REPLACE(valeur_fonciere, ',', '')::numeric /
NULLIF(GREATEST(
    CASE WHEN surface_carrez_1 ~ '^[\d,]+\.?\d*$' THEN ... END,
    CASE WHEN surface_reelle_bati ~ '^[\d,]+\.?\d*$' THEN ... END
), 0)
```
- Calculates: `price / surface_area`
- Uses largest available surface (Carrez or built)
- **Division by zero protection**: `NULLIF(..., 0)` returns NULL if surface is 0
- Only calculated if both price and surface are valid

#### 6. **Property Type Filtering**
```sql
WHERE type_local IN ('Appartement', 'Maison')
```
- **Included**: Apartments and houses only
- **Excluded**: Commercial properties, garages, parking spaces, land plots, dependencies

#### 7. **Data Quality Filters**
All imported records must satisfy:
- Valid date format and parseable date
- Valid price format and `price > 0`
- Property type is `Appartement` or `Maison`
- Postal code exists and not empty
- **Note**: Surface area is NOT required (some sales don't include it)

#### 8. **Metadata Generation**
- `data_year`: Year extracted from filename (2021-2025)
- `source_file`: Path to original DVF file
- `import_batch_id`: UUID for this import batch (for audit trail)
- `transaction_group_id`: MD5 hash of (date, price, postal, address) for grouping
- `raw_data`: JSON with additional fields for reference

#### 9. **Deduplication Strategy**
```sql
ON CONFLICT (sale_date, sale_price, address, postal_code, surface_area) DO NOTHING
```
- Unique constraint on 5 fields (business key for property sales)
- Silently skips duplicates on re-import
- Allows safe re-running of import scripts

## Data Statistics

After full import (2021-2025):

```
 data_year | record_count | appartements | maisons | earliest_sale | latest_sale
-----------+--------------+--------------+---------+---------------+-------------
      2021 |    1,292,403 |      604,745 | 687,658 | 2021-01-01    | 2021-12-31
      2022 |    1,236,707 |      602,168 | 634,539 | 2022-01-01    | 2022-12-31
      2023 |      959,391 |      462,793 | 496,598 | 2023-01-02    | 2023-12-31
      2024 |      859,590 |      402,783 | 456,807 | 2024-01-01    | 2024-12-31
      2025 |      352,192 |      169,894 | 182,298 | 2025-01-01    | 2025-06-30

TOTAL: 4,700,283 records (~4.2 GB database size)
```

## Common Issues

### Issue: Container Not Running

```bash
ERROR: Database container 'appartment-agent-db-1' is not running!
```

**Solution**:
```bash
docker-compose up -d
```

### Issue: File Not Found

```bash
WARNING: File not found: /Users/carrefour/appartment-agent/data/dvf/ValeursFoncieres-2023.txt
```

**Solution**: Ensure DVF files are in `/Users/carrefour/appartment-agent/data/dvf/`

### Issue: Duplicate Records

If you run the import twice, duplicates are automatically skipped due to the `ON CONFLICT` clause.

## Comparison: Old vs New Method

| Method | Tool | Time | Records/sec |
|--------|------|------|-------------|
| **Old** | Python + Pandas + ORM | 2-3 hours | ~300-500 |
| **New** | PostgreSQL COPY | 7 minutes | ~11,000 |

**Speed improvement**: ~20-30x faster

## Files Location

- DVF data: `/Users/carrefour/appartment-agent/data/dvf/`
- Scripts: `/Users/carrefour/appartment-agent/backend/scripts/`

## Advanced Usage

### Import Single Year

```bash
./scripts/test_import_2023_v2.sh
```

### Delete All Records Only

```bash
docker exec -i appartment-agent-db-1 psql -U appartment -d appartment_agent < scripts/delete_all_dvf.sql
```

### Check Import Progress

While import is running, check record counts:

```bash
docker exec appartment-agent-db-1 psql -U appartment -d appartment_agent -c "
SELECT data_year, COUNT(*) FROM dvf_records GROUP BY data_year ORDER BY data_year;
"
```

## Why This is the Fastest Method

1. **No Network Overhead**: Server-side `COPY` reads files directly
2. **No Row-by-Row Processing**: Bulk load instead of INSERT loops
3. **No WAL for Staging**: UNLOGGED table skips write-ahead log
4. **Minimal Parsing**: Direct copy into text columns, transform later
5. **Batch Commits**: Single transaction per file
6. **Disabled Triggers**: No constraint checking during load

## Next Steps

After import, you can:
- Query records: `SELECT * FROM dvf_records WHERE postal_code = '75006' LIMIT 10;`
- Use address search: `SELECT * FROM dvf_records WHERE address LIKE '%RUE DE SEVRES%';`
- Analyze price trends: `SELECT data_year, AVG(price_per_sqm) FROM dvf_records GROUP BY data_year;`

---

## ⚠️ IMPORTANT TODO: Data Validation & Quality Checks

While the import is **fast and functional**, comprehensive data quality validation is **CRITICAL** before using this data in production.

### 🔍 **Required Data Quality Validation**

#### **1. Statistical Outlier Detection**

**Priority: CRITICAL**

Run advanced EDA to detect and handle outliers:

```sql
-- Check for extreme prices (potential data errors)
SELECT
    data_year,
    COUNT(*) FILTER (WHERE sale_price > 100000000) as "prices_over_100M",
    COUNT(*) FILTER (WHERE sale_price < 10000) as "prices_under_10K",
    COUNT(*) FILTER (WHERE price_per_sqm > 50000) as "price_sqm_over_50K",
    COUNT(*) FILTER (WHERE price_per_sqm < 100) as "price_sqm_under_100"
FROM dvf_records
GROUP BY data_year;
```

**TODO Actions**:
- [ ] Identify outlier thresholds (use IQR or Z-score method)
- [ ] Investigate extreme values (are they errors or legitimate luxury properties?)
- [ ] Add outlier flags to database schema (`is_outlier` boolean column)
- [ ] Document outlier handling strategy (exclude, cap, or flag?)

#### **2. Missing Data Analysis**

**Priority: HIGH**

Check completeness of critical fields:

```sql
-- Missing data analysis
SELECT
    data_year,
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE surface_area IS NULL) as missing_surface,
    COUNT(*) FILTER (WHERE rooms IS NULL) as missing_rooms,
    COUNT(*) FILTER (WHERE price_per_sqm IS NULL) as missing_price_sqm,
    ROUND(100.0 * COUNT(*) FILTER (WHERE surface_area IS NULL) / COUNT(*), 2) as pct_missing_surface
FROM dvf_records
GROUP BY data_year;
```

**TODO Actions**:
- [ ] Quantify missing data by year and field
- [ ] Determine if missing data is MCAR (completely random) or systematic
- [ ] Decide on imputation strategy (drop, mean/median fill, or flag)
- [ ] Document impact on price analysis (e.g., can't calculate price/sqm without surface)

#### **3. Address Data Quality**

**Priority: HIGH**

Validate address normalization and completeness:

```sql
-- Check address quality
SELECT
    COUNT(*) FILTER (WHERE address = '' OR address IS NULL) as empty_addresses,
    COUNT(*) FILTER (WHERE LENGTH(address) < 5) as suspiciously_short,
    COUNT(*) FILTER (WHERE address NOT LIKE '% %') as missing_components,
    COUNT(*) FILTER (WHERE city IS NULL OR city = '') as missing_city,
    COUNT(*) FILTER (WHERE postal_code IS NULL OR postal_code = '') as missing_postal
FROM dvf_records;
```

**TODO Actions**:
- [ ] Validate address geocoding accuracy (if needed for mapping)
- [ ] Check for duplicate addresses with vastly different prices (data errors?)
- [ ] Implement address standardization (upper/lower case, abbreviations)
- [ ] Consider using French address validation API (e.g., BAN - Base Adresse Nationale)

#### **4. Price Distribution Analysis**

**Priority: CRITICAL**

Analyze price distributions for anomalies:

```sql
-- Price distribution percentiles
SELECT
    data_year,
    property_type,
    PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY sale_price) as p01,
    PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY sale_price) as p05,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY sale_price) as p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY sale_price) as median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY sale_price) as p75,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY sale_price) as p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY sale_price) as p99
FROM dvf_records
WHERE sale_price IS NOT NULL
GROUP BY data_year, property_type;
```

**TODO Actions**:
- [ ] Identify unrealistic prices (typos, data entry errors)
- [ ] Check for clustering around round numbers (indication of estimates vs actual prices)
- [ ] Validate price trends year-over-year (should match known market trends)
- [ ] Cross-reference with external sources (INSEE, notaires.fr statistics)

#### **5. Surface Area Validation**

**Priority: HIGH**

Validate surface area distributions:

```sql
-- Surface area distribution
SELECT
    property_type,
    COUNT(*) as total,
    ROUND(AVG(surface_area), 2) as avg_surface,
    ROUND(STDDEV(surface_area), 2) as stddev_surface,
    MIN(surface_area) as min_surface,
    MAX(surface_area) as max_surface,
    COUNT(*) FILTER (WHERE surface_area < 10) as "under_10_sqm",
    COUNT(*) FILTER (WHERE surface_area > 500) as "over_500_sqm"
FROM dvf_records
WHERE surface_area IS NOT NULL
GROUP BY property_type;
```

**TODO Actions**:
- [ ] Investigate extremely small surfaces (<10 sqm) - studios or errors?
- [ ] Investigate extremely large surfaces (>500 sqm) - mansions or data errors?
- [ ] Validate Carrez vs built surface discrepancies
- [ ] Check for surface/room count consistency (e.g., 1-room with 200 sqm?)

#### **6. Temporal Analysis**

**Priority: MEDIUM**

Check for seasonal patterns and anomalies:

```sql
-- Sales by month
SELECT
    EXTRACT(MONTH FROM sale_date) as month,
    COUNT(*) as sales_count,
    ROUND(AVG(sale_price), 2) as avg_price
FROM dvf_records
WHERE EXTRACT(YEAR FROM sale_date) = 2024
GROUP BY EXTRACT(MONTH FROM sale_date)
ORDER BY month;
```

**TODO Actions**:
- [ ] Validate seasonal patterns (summer slowdown, year-end rush)
- [ ] Check for data gaps (missing months or years)
- [ ] Identify anomalous spikes or drops (could indicate incomplete data)

#### **7. Geographic Distribution**

**Priority: MEDIUM**

Validate geographic coverage:

```sql
-- Top departments and cities
SELECT
    department,
    COUNT(*) as sales_count,
    COUNT(DISTINCT city) as num_cities,
    ROUND(AVG(price_per_sqm) FILTER (WHERE price_per_sqm > 0), 2) as avg_price_sqm
FROM dvf_records
GROUP BY department
ORDER BY sales_count DESC
LIMIT 20;
```

**TODO Actions**:
- [ ] Verify coverage matches French geography (all departments represented?)
- [ ] Check for urban/rural bias (Paris over-represented?)
- [ ] Validate price/sqm by department against known market values
- [ ] Identify departments with suspiciously low data (import issues?)

#### **8. Price/Sqm Reasonableness**

**Priority: CRITICAL**

Validate calculated price per sqm:

```sql
-- Price per sqm by major cities
SELECT
    city,
    postal_code,
    COUNT(*) as sales,
    ROUND(AVG(price_per_sqm), 2) as avg_price_sqm,
    ROUND(MIN(price_per_sqm), 2) as min_price_sqm,
    ROUND(MAX(price_per_sqm), 2) as max_price_sqm
FROM dvf_records
WHERE price_per_sqm > 0
  AND city IN ('PARIS 06', 'PARIS 16', 'LYON', 'MARSEILLE', 'BORDEAUX')
GROUP BY city, postal_code
ORDER BY avg_price_sqm DESC
LIMIT 20;
```

**TODO Actions**:
- [ ] Compare against known benchmarks (e.g., Paris 6th should be 12K-18K €/sqm)
- [ ] Flag records where price/sqm deviates >3 standard deviations from area mean
- [ ] Check for calculation errors (price/surface formula issues)

#### **9. Duplicate Detection (Beyond Import)**

**Priority: MEDIUM**

Check for near-duplicates that passed the unique constraint:

```sql
-- Find potential duplicates with slight variations
SELECT
    address,
    postal_code,
    sale_date,
    COUNT(*) as occurrence_count,
    ARRAY_AGG(DISTINCT sale_price ORDER BY sale_price) as prices,
    ARRAY_AGG(DISTINCT surface_area ORDER BY surface_area) as surfaces
FROM dvf_records
GROUP BY address, postal_code, sale_date
HAVING COUNT(*) > 1
LIMIT 100;
```

**TODO Actions**:
- [ ] Investigate records with same date/address but different prices
- [ ] Check if these are legitimate multi-unit sales vs data errors
- [ ] Consider fuzzy address matching for duplicate detection

#### **10. Business Logic Validation**

**Priority: HIGH**

Validate against domain knowledge:

**TODO Actions**:
- [ ] Cross-validate with official DVF statistics published by French government
- [ ] Compare total record counts by year with government reports
- [ ] Validate average prices against INSEE housing price index
- [ ] Check if Paris price trends match notaires.fr publications
- [ ] Validate number of Appartement vs Maison ratio by region

---

### 📊 **Recommended EDA Workflow**

1. **Create a Jupyter notebook** for exploratory data analysis:
   ```bash
   /Users/carrefour/appartment-agent/backend/notebooks/dvf_eda.ipynb
   ```

2. **Generate automated data quality report** using libraries like:
   - `pandas-profiling` (now `ydata-profiling`)
   - `great-expectations`
   - `dataprep.eda`

3. **Visualizations to create**:
   - Price distributions by year (histograms, box plots)
   - Price/sqm heatmap by department
   - Time series of average prices
   - Scatter plots: surface vs price (by property type)
   - Missing data heatmap
   - Correlation matrix

4. **Statistical tests to run**:
   - Shapiro-Wilk test for normality of price distributions
   - ANOVA for price differences across years
   - Chi-square test for categorical distributions

---

### 🚨 **Data Quality Flags to Add**

Consider adding these columns to improve data usability:

```sql
ALTER TABLE dvf_records ADD COLUMN data_quality_score INTEGER;
ALTER TABLE dvf_records ADD COLUMN is_outlier BOOLEAN DEFAULT FALSE;
ALTER TABLE dvf_records ADD COLUMN has_complete_data BOOLEAN DEFAULT FALSE;
ALTER TABLE dvf_records ADD COLUMN quality_notes TEXT;

-- Example update:
UPDATE dvf_records SET
    has_complete_data = (
        sale_price IS NOT NULL AND
        surface_area IS NOT NULL AND
        address IS NOT NULL AND address != '' AND
        rooms IS NOT NULL
    );
```

---

### 📝 **Next Steps for Production Readiness**

Before using this data for critical property analysis:

1. **Run all validation queries** above and document results
2. **Create data quality dashboard** (e.g., Metabase, Grafana)
3. **Implement automated quality checks** on each import
4. **Document known data issues** and handling strategies
5. **Set up alerts** for anomalous imports (e.g., <1M records for full year)
6. **Create cleaned dataset** (e.g., `dvf_records_clean` view with filters)
7. **Version your data** (track import batch IDs for rollback)

---

## Credits

Based on PostgreSQL best practices for bulk data loading.

**Data Source**: [DVF Open Data](https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/) - French government property transaction data.
