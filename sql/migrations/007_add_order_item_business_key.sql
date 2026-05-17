-- SellerDataPipeline migration 007: add order item business key.
-- Created: 2026-05-17
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason:
--   GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL -> amazon_order_item
--   needs a stable idempotency key for MERGE/upsert. source_row_hash changes
--   when mutable attributes such as order status, item status, shipping fields,
--   taxes, prices, or promotion fields change, so it must not be used as the
--   business upsert key.
--
-- Intended business key:
--   marketplace_id + source_report_type + amazon_order_id + seller_sku + asin
--   + purchase_date_raw
--
-- Safety:
--   001_create_core_tables.sql, 002_create_indexes.sql,
--   003_add_listing_snapshot_business_key_hash.sql,
--   004_add_inventory_daily_business_key_hash.sql,
--   005_add_sales_traffic_business_key_hashes.sql, and
--   006_add_settlement_transaction_business_key.sql have already been executed
--   and must not be edited. This migration is intentionally additive. The new
--   columns are nullable and the unique index is filtered so the migration
--   remains safe even if the table is no longer empty when executed.
--   Repository code must still require source_row_index and business_key_hash
--   for rows it writes.

/* =========================================================
   1. Precondition
   ========================================================= */

IF OBJECT_ID('dbo.amazon_order_item', 'U') IS NULL
BEGIN
    THROW 50008, 'Required table dbo.amazon_order_item does not exist. Run 001_create_core_tables.sql before migration 007.', 1;
END;
GO

/* =========================================================
   2. Add source row index column
   ========================================================= */

IF COL_LENGTH('dbo.amazon_order_item', 'source_row_index') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_order_item
    ADD source_row_index INT NULL;
END;
GO

/* =========================================================
   3. Add stable business upsert key column
   ========================================================= */

IF COL_LENGTH('dbo.amazon_order_item', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_order_item
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

/* =========================================================
   4. Add unique filtered index for populated business keys
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_order_item')
      AND name = 'UX_amazon_order_item_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_order_item_business_key_hash
    ON dbo.amazon_order_item (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO
