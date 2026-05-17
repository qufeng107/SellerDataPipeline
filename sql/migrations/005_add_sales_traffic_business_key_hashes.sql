-- SellerDataPipeline migration 005: add sales traffic business key hashes.
-- Created: 2026-05-17
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason:
--   GET_SALES_AND_TRAFFIC_REPORT writes two normalized target tables:
--   dbo.amazon_sales_traffic_daily and dbo.amazon_sales_traffic_asin_daily.
--   Both need stable idempotency keys for MERGE/upsert. source_row_hash changes
--   when mutable sales/traffic metrics change, so it must not be used as the
--   business upsert key.
--
-- Intended daily business key:
--   marketplace_id + report_date + date_granularity
--
-- Intended ASIN business key:
--   marketplace_id + report_start_date + report_end_date + asin_granularity
--   + parent_asin + child_asin
--
-- Safety:
--   001_create_core_tables.sql, 002_create_indexes.sql,
--   003_add_listing_snapshot_business_key_hash.sql, and
--   004_add_inventory_daily_business_key_hash.sql have already been executed
--   and must not be edited. This migration is intentionally additive. The new
--   columns are nullable and the unique indexes are filtered so the migration
--   remains safe even if the tables are no longer empty when executed.
--   Repository code must still require business_key_hash for rows it writes.

/* =========================================================
   1. Preconditions
   ========================================================= */

IF OBJECT_ID('dbo.amazon_sales_traffic_daily', 'U') IS NULL
BEGIN
    THROW 50005, 'Required table dbo.amazon_sales_traffic_daily does not exist. Run 001_create_core_tables.sql before migration 005.', 1;
END;

IF OBJECT_ID('dbo.amazon_sales_traffic_asin_daily', 'U') IS NULL
BEGIN
    THROW 50006, 'Required table dbo.amazon_sales_traffic_asin_daily does not exist. Run 001_create_core_tables.sql before migration 005.', 1;
END;
GO

/* =========================================================
   2. Add stable business upsert key column to daily table
   ========================================================= */

IF COL_LENGTH('dbo.amazon_sales_traffic_daily', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_sales_traffic_daily
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

/* =========================================================
   3. Add stable business upsert key column to ASIN table
   ========================================================= */

IF COL_LENGTH('dbo.amazon_sales_traffic_asin_daily', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_sales_traffic_asin_daily
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

/* =========================================================
   4. Add unique filtered index for populated daily business keys
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_sales_traffic_daily')
      AND name = 'UX_amazon_sales_traffic_daily_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_sales_traffic_daily_business_key_hash
    ON dbo.amazon_sales_traffic_daily (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO

/* =========================================================
   5. Add unique filtered index for populated ASIN business keys
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_sales_traffic_asin_daily')
      AND name = 'UX_amazon_sales_traffic_asin_daily_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_sales_traffic_asin_daily_business_key_hash
    ON dbo.amazon_sales_traffic_asin_daily (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO
