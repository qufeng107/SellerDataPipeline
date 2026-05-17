-- SellerDataPipeline migration 011: add inventory ledger business keys.
--
-- Context:
-- - 001_create_core_tables.sql created inventory ledger tables before the
--   project standardized on business_key_hash based MERGE/upsert.
-- - This migration adds source_row_index and business_key_hash to summary/detail
--   ledger tables and creates filtered unique indexes.
-- - Historical migrations 001-010 must not be edited after execution.

/* =========================================================
   Inventory ledger summary rows
   ========================================================= */

IF COL_LENGTH('dbo.amazon_inventory_ledger_summary_daily', 'source_row_index') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_inventory_ledger_summary_daily
    ADD source_row_index INT NULL;
END;

IF COL_LENGTH('dbo.amazon_inventory_ledger_summary_daily', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_inventory_ledger_summary_daily
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_inventory_ledger_summary_daily')
      AND name = 'UX_amazon_inventory_ledger_summary_daily_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_inventory_ledger_summary_daily_business_key_hash
    ON dbo.amazon_inventory_ledger_summary_daily (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO

/* =========================================================
   Inventory ledger detail rows
   ========================================================= */

IF COL_LENGTH('dbo.amazon_inventory_ledger_detail', 'source_row_index') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_inventory_ledger_detail
    ADD source_row_index INT NULL;
END;

IF COL_LENGTH('dbo.amazon_inventory_ledger_detail', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_inventory_ledger_detail
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_inventory_ledger_detail')
      AND name = 'UX_amazon_inventory_ledger_detail_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_inventory_ledger_detail_business_key_hash
    ON dbo.amazon_inventory_ledger_detail (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO
