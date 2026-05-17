-- SellerDataPipeline migration 004: add inventory daily business key hash.
-- Created: 2026-05-17
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason:
--   GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA -> amazon_inventory_daily
--   needs a stable idempotency key for MERGE/upsert. source_row_hash changes
--   when mutable inventory metrics change, so it must not be used as the
--   business upsert key.
--
-- Intended business key:
--   marketplace_id + snapshot_date + seller_sku + fnsku + asin
--
-- Safety:
--   001_create_core_tables.sql, 002_create_indexes.sql, and
--   003_add_listing_snapshot_business_key_hash.sql have already been executed
--   and must not be edited. This migration is intentionally additive. The new
--   column is nullable and the unique index is filtered so the migration remains
--   safe even if the table is no longer empty when executed. Repository code
--   must still require business_key_hash for rows it writes.

/* =========================================================
   1. Precondition
   ========================================================= */

IF OBJECT_ID('dbo.amazon_inventory_daily', 'U') IS NULL
BEGIN
    THROW 50004, 'Required table dbo.amazon_inventory_daily does not exist. Run 001_create_core_tables.sql before migration 004.', 1;
END;
GO

/* =========================================================
   2. Add stable business upsert key column
   ========================================================= */

IF COL_LENGTH('dbo.amazon_inventory_daily', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_inventory_daily
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

/* =========================================================
   3. Add unique filtered index for populated business keys
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_inventory_daily')
      AND name = 'UX_amazon_inventory_daily_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_inventory_daily_business_key_hash
    ON dbo.amazon_inventory_daily (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO
