-- SellerDataPipeline migration 016: Finances API natural-month transaction ledger.
-- v1.90. Additive only; historical migrations must not be edited.

IF OBJECT_ID('dbo.amazon_finance_transaction', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_finance_transaction (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_finance_transaction PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        transaction_id NVARCHAR(200) NOT NULL,
        transaction_status NVARCHAR(50) NOT NULL,
        transaction_type NVARCHAR(100) NOT NULL,
        description NVARCHAR(1000) NULL,
        posted_at_utc DATETIME2 NOT NULL,
        posted_at_local DATETIME2 NOT NULL,
        posted_date_local DATE NOT NULL,
        marketplace_timezone NVARCHAR(100) NOT NULL,
        amount DECIMAL(18,4) NOT NULL,
        currency NVARCHAR(10) NULL,
        settlement_id NVARCHAR(200) NULL,
        order_id NVARCHAR(200) NULL,
        deferred_transaction_id NVARCHAR(200) NULL,
        release_transaction_id NVARCHAR(200) NULL,
        management_role NVARCHAR(100) NOT NULL,
        management_include BIT NOT NULL,
        management_replace_with_ads_api BIT NOT NULL,
        review_required BIT NOT NULL,
        product_sales_amount DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_product_sales DEFAULT 0,
        shipping_amount DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_shipping DEFAULT 0,
        promotion_amount DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_promotion DEFAULT 0,
        fba_fulfillment_fee DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_fba DEFAULT 0,
        shipping_chargeback DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_ship_cb DEFAULT 0,
        refund_product_amount DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_refund_product DEFAULT 0,
        refund_shipping_amount DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_refund_shipping DEFAULT 0,
        refund_promotion_amount DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_refund_promo DEFAULT 0,
        liquidation_revenue DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_liq_rev DEFAULT 0,
        liquidation_fee DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_liq_fee DEFAULT 0,
        subscription_fee DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_subscription DEFAULT 0,
        coupon_fee DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_coupon DEFAULT 0,
        deal_fee DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_deal DEFAULT 0,
        storage_fee DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_storage DEFAULT 0,
        customer_return_fee DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_customer_return DEFAULT 0,
        other_service_fee DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_finance_transaction_other_service DEFAULT 0,
        unit_events_json NVARCHAR(MAX) NOT NULL,
        related_identifiers_json NVARCHAR(MAX) NOT NULL,
        raw_transaction_json NVARCHAR(MAX) NOT NULL,
        raw_transaction_hash NVARCHAR(100) NOT NULL,
        business_key_hash NVARCHAR(100) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_finance_transaction_created DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_finance_transaction_updated DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_finance_transaction')
      AND name = 'UX_amazon_finance_transaction_business_key_hash'
)
BEGIN
    CREATE UNIQUE INDEX UX_amazon_finance_transaction_business_key_hash
    ON dbo.amazon_finance_transaction (business_key_hash);
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_finance_transaction')
      AND name = 'IX_amazon_finance_transaction_marketplace_local_date'
)
BEGIN
    CREATE INDEX IX_amazon_finance_transaction_marketplace_local_date
    ON dbo.amazon_finance_transaction (marketplace_id, posted_date_local)
    INCLUDE (transaction_type, transaction_status, amount, currency, management_include, review_required);
END;
GO
