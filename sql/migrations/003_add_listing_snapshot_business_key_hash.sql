-- SellerDataPipeline migration 003: add listing snapshot business key hash.
-- Created: 2026-05-16
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason:
--   GET_MERCHANT_LISTINGS_ALL_DATA -> amazon_listing_snapshot needs a stable
--   idempotency key for MERGE/upsert. source_row_hash changes when mutable
--   attributes such as price/title/status change, so it must not be used as
--   the business upsert key.
--
-- Safety:
--   001_create_core_tables.sql and 002_create_indexes.sql have already been
--   executed and must not be edited. This migration is intentionally additive.
--   The new column is nullable and the unique index is filtered so the migration
--   remains safe even if the table is no longer empty when executed. Repository
--   code must still require business_key_hash for rows it writes.

/* =========================================================
   1. Precondition
   ========================================================= */

IF OBJECT_ID('dbo.amazon_listing_snapshot', 'U') IS NULL
BEGIN
    THROW 50003, 'Required table dbo.amazon_listing_snapshot does not exist. Run 001_create_core_tables.sql before migration 003.', 1;
END;
GO

/* =========================================================
   2. Add stable business upsert key column
   ========================================================= */

IF COL_LENGTH('dbo.amazon_listing_snapshot', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_listing_snapshot
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

/* =========================================================
   3. Add unique filtered index for populated business keys
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_listing_snapshot')
      AND name = 'UX_amazon_listing_snapshot_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_listing_snapshot_business_key_hash
    ON dbo.amazon_listing_snapshot (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO
