-- SellerDataPipeline migration 010: add promotion and coupon business keys.
--
-- Context:
-- - 001_create_core_tables.sql created promotion/coupon target tables before the
--   project standardized on business_key_hash based MERGE/upsert.
-- - This migration adds source_row_index and business_key_hash to the four
--   promotion/coupon normalized tables and creates filtered unique indexes.
-- - Historical migrations 001-009 must not be edited.

/* =========================================================
   Promotion performance main rows
   ========================================================= */

IF COL_LENGTH('dbo.amazon_promotion_performance', 'source_row_index') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_promotion_performance
    ADD source_row_index INT NULL;
END;

IF COL_LENGTH('dbo.amazon_promotion_performance', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_promotion_performance
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_promotion_performance')
      AND name = 'UX_amazon_promotion_performance_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_promotion_performance_business_key_hash
    ON dbo.amazon_promotion_performance (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO

/* =========================================================
   Promotion included product rows
   ========================================================= */

IF COL_LENGTH('dbo.amazon_promotion_product_performance', 'source_row_index') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_promotion_product_performance
    ADD source_row_index INT NULL;
END;

IF COL_LENGTH('dbo.amazon_promotion_product_performance', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_promotion_product_performance
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_promotion_product_performance')
      AND name = 'UX_amazon_promotion_product_performance_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_promotion_product_performance_business_key_hash
    ON dbo.amazon_promotion_product_performance (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO

/* =========================================================
   Coupon performance main rows
   ========================================================= */

IF COL_LENGTH('dbo.amazon_coupon_performance', 'source_row_index') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_coupon_performance
    ADD source_row_index INT NULL;
END;

IF COL_LENGTH('dbo.amazon_coupon_performance', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_coupon_performance
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_coupon_performance')
      AND name = 'UX_amazon_coupon_performance_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_coupon_performance_business_key_hash
    ON dbo.amazon_coupon_performance (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO

/* =========================================================
   Coupon ASIN rows
   ========================================================= */

IF COL_LENGTH('dbo.amazon_coupon_asin', 'source_row_index') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_coupon_asin
    ADD source_row_index INT NULL;
END;

IF COL_LENGTH('dbo.amazon_coupon_asin', 'business_key_hash') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_coupon_asin
    ADD business_key_hash NVARCHAR(100) NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_coupon_asin')
      AND name = 'UX_amazon_coupon_asin_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_coupon_asin_business_key_hash
    ON dbo.amazon_coupon_asin (business_key_hash)
    WHERE business_key_hash IS NOT NULL;
END;
GO
