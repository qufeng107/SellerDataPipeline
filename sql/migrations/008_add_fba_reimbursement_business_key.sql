-- SellerDataPipeline migration 008: add FBA reimbursement business key.
-- Created: 2026-05-17
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason:
--   GET_FBA_REIMBURSEMENTS_DATA -> amazon_fba_reimbursement needs a
--   stable idempotency key for MERGE/upsert. source_row_hash changes when
--   mutable descriptive fields or raw formatting changes, so it must not be
--   used as the business upsert key.
--
-- Intended business key:
--   marketplace_id + source_report_type + reimbursement_id + seller_sku
--   + fnsku + asin + approval_date_raw + amount_total
--   + quantity_reimbursed_total
--
-- Safety:
--   001_create_core_tables.sql, 002_create_indexes.sql,
--   003_add_listing_snapshot_business_key_hash.sql,
--   004_add_inventory_daily_business_key_hash.sql,
--   005_add_sales_traffic_business_key_hashes.sql,
--   006_add_settlement_transaction_business_key.sql, and
--   007_add_order_item_business_key.sql have already been executed and must
--   not be edited. This migration is intentionally additive. The new columns
--   are nullable and the unique index is filtered so the migration remains
--   safe even if the table is no longer empty when executed. Repository code
--   must still require source_row_index and business_key_hash for rows it
--   writes.

/* =========================================================
   1. Precondition
   ========================================================= */

IF OBJECT_ID('dbo.amazon_fba_reimbursement', 'U') IS NULL
BEGIN
    THROW 50009, 'Required table dbo.amazon_fba_reimbursement does not exist. Run 001_create_core_tables.sql before migration 008.', 1;
END;
GO

/* =========================================================
   2. Add source row index column
   ========================================================= */

IF COL_LENGTH('dbo.amazon_fba_reimbursement', 'source_row_index') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_fba_reimbursement
    ADD source_row_index INT NULL;
END;
GO

/* =========================================================
   3. Add stable business upsert key column
   ========================================================= */

IF COL_LENGTH('dbo.amazon_fba_reimbursement', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_fba_reimbursement
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

/* =========================================================
   4. Add unique filtered index for populated business keys
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_fba_reimbursement')
      AND name = 'UX_amazon_fba_reimbursement_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_fba_reimbursement_business_key_hash
    ON dbo.amazon_fba_reimbursement (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO
