-- Initial indexes. Adjust after real data volume and query patterns are known.

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_amazon_report_request_status')
    CREATE INDEX IX_amazon_report_request_status
    ON dbo.amazon_report_request (processing_status, download_status, parse_status, requested_at);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_amazon_sales_daily_key')
    CREATE INDEX IX_amazon_sales_daily_key
    ON dbo.amazon_sales_daily (marketplace, sales_date, sku, asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_amazon_finance_event_date')
    CREATE INDEX IX_amazon_finance_event_date
    ON dbo.amazon_finance_event (marketplace, posted_date, order_id, sku);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_amazon_ads_daily_key')
    CREATE INDEX IX_amazon_ads_daily_key
    ON dbo.amazon_ads_daily (marketplace, ads_date, campaign_id, ad_group_id, sku, asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_amazon_inventory_daily_key')
    CREATE INDEX IX_amazon_inventory_daily_key
    ON dbo.amazon_inventory_daily (marketplace, inventory_date, sku, asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_amazon_periodic_report_snapshot_key')
    CREATE INDEX IX_amazon_periodic_report_snapshot_key
    ON dbo.amazon_periodic_report_snapshot (marketplace, period_type, period_start, period_end, version);
GO
