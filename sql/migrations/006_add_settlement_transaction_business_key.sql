-- SellerDataPipeline migration 006: add settlement transaction business key.
-- Created: 2026-05-17
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason:
--   GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2 -> amazon_settlement_transaction
--   needs a stable idempotency key for MERGE/upsert. Settlement files can
--   contain repeated rows with the same settlement/order/SKU/amount attributes,
--   so source_row_hash alone is not sufficient for stable row identity.
--
-- Intended business key:
--   marketplace_id + source_report_id + source_raw_file_path + source_row_index
--   + source_row_hash
--
-- Safety:
--   001_create_core_tables.sql, 002_create_indexes.sql,
--   003_add_listing_snapshot_business_key_hash.sql,
--   004_add_inventory_daily_business_key_hash.sql, and
--   005_add_sales_traffic_business_key_hashes.sql have already been executed
--   and must not be edited. This migration is intentionally additive. The new
--   columns are nullable and the unique index is filtered so the migration
--   remains safe even if the table is no longer empty when executed.
--   Repository code must still require source_row_index and business_key_hash
--   for rows it writes.

/* =========================================================
   1. Precondition
   ========================================================= */

IF OBJECT_ID('dbo.amazon_settlement_transaction', 'U') IS NULL
BEGIN
    THROW 50007, 'Required table dbo.amazon_settlement_transaction does not exist. Run 001_create_core_tables.sql before migration 006.', 1;
END;
GO

/* =========================================================
   2. Add source row index column
   ========================================================= */

IF COL_LENGTH('dbo.amazon_settlement_transaction', 'source_row_index') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_settlement_transaction
    ADD source_row_index INT NULL;
END;
GO

/* =========================================================
   3. Add stable business upsert key column
   ========================================================= */

IF COL_LENGTH('dbo.amazon_settlement_transaction', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_settlement_transaction
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

/* =========================================================
   4. Add unique filtered index for populated business keys
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_settlement_transaction')
      AND name = 'UX_amazon_settlement_transaction_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_settlement_transaction_business_key_hash
    ON dbo.amazon_settlement_transaction (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO
