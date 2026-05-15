-- SellerDataPipeline initial indexes for Azure SQL Database.
-- Version: v1.13 Ads ingestion dry-run guard draft
-- Status: NOT executed yet. Review manually before running against Azure SQL.
-- Notes:
--   * Unique business keys are intentionally conservative because Amazon report rows
--     may contain NULL identifiers or late adjustments.
--   * Repository upsert code should still prefer deterministic natural keys where stable,
--     and fall back to source_report_id + source_row_hash where necessary.

/* =========================================================
   L0/L1 indexes
   ========================================================= */

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_marketplace') AND name = 'UX_amazon_marketplace_marketplace_id')
    CREATE UNIQUE INDEX UX_amazon_marketplace_marketplace_id
    ON dbo.amazon_marketplace (marketplace_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_sync_run_log') AND name = 'IX_amazon_sync_run_log_job_started')
    CREATE INDEX IX_amazon_sync_run_log_job_started
    ON dbo.amazon_sync_run_log (job_name, started_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_sync_run_log') AND name = 'IX_amazon_sync_run_log_status_started')
    CREATE INDEX IX_amazon_sync_run_log_status_started
    ON dbo.amazon_sync_run_log (status, started_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_sync_run_log') AND name = 'IX_amazon_sync_run_log_workflow_started')
    CREATE INDEX IX_amazon_sync_run_log_workflow_started
    ON dbo.amazon_sync_run_log (workflow_name, started_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_report_request') AND name = 'UX_amazon_report_request_report_id')
    CREATE UNIQUE INDEX UX_amazon_report_request_report_id
    ON dbo.amazon_report_request (marketplace_id, source_system, report_type, report_id)
    WHERE report_id IS NOT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_report_request') AND name = 'IX_amazon_report_request_status')
    CREATE INDEX IX_amazon_report_request_status
    ON dbo.amazon_report_request (processing_status, download_status, parse_status, requested_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_report_request') AND name = 'IX_amazon_report_request_type_range')
    CREATE INDEX IX_amazon_report_request_type_range
    ON dbo.amazon_report_request (source_system, report_type, marketplace_id, data_start_time, data_end_time);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_raw_report_file') AND name = 'UX_amazon_raw_report_file_path')
    CREATE UNIQUE INDEX UX_amazon_raw_report_file_path
    ON dbo.amazon_raw_report_file (storage_backend, file_path);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_raw_report_file') AND name = 'IX_amazon_raw_report_file_report')
    CREATE INDEX IX_amazon_raw_report_file_report
    ON dbo.amazon_raw_report_file (source_system, report_type, marketplace_id, downloaded_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_raw_report_file') AND name = 'IX_amazon_raw_report_file_sha256')
    CREATE INDEX IX_amazon_raw_report_file_sha256
    ON dbo.amazon_raw_report_file (sha256);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_report_field_catalog') AND name = 'IX_amazon_report_field_catalog_report')
    CREATE INDEX IX_amazon_report_field_catalog_report
    ON dbo.amazon_report_field_catalog (source_system, report_type, marketplace_id, field_position);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_sku_cost') AND name = 'IX_amazon_sku_cost_effective')
    CREATE INDEX IX_amazon_sku_cost_effective
    ON dbo.amazon_sku_cost (marketplace_id, seller_sku, effective_from, effective_to);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_schema_validation_event') AND name = 'IX_amazon_schema_validation_event_report')
    CREATE INDEX IX_amazon_schema_validation_event_report
    ON dbo.amazon_schema_validation_event (source_system, report_type, marketplace_id, created_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_schema_validation_event') AND name = 'IX_amazon_schema_validation_event_review')
    CREATE INDEX IX_amazon_schema_validation_event_review
    ON dbo.amazon_schema_validation_event (requires_review, notification_status, created_at DESC);
GO

/* =========================================================
   L3 common source-trace indexes
   ========================================================= */

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_listing_snapshot') AND name = 'IX_amazon_listing_snapshot_key')
    CREATE INDEX IX_amazon_listing_snapshot_key
    ON dbo.amazon_listing_snapshot (marketplace_id, snapshot_date DESC, seller_sku, listing_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_listing_snapshot') AND name = 'IX_amazon_listing_snapshot_source')
    CREATE INDEX IX_amazon_listing_snapshot_source
    ON dbo.amazon_listing_snapshot (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_inventory_daily') AND name = 'IX_amazon_inventory_daily_key')
    CREATE INDEX IX_amazon_inventory_daily_key
    ON dbo.amazon_inventory_daily (marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_inventory_daily') AND name = 'IX_amazon_inventory_daily_source')
    CREATE INDEX IX_amazon_inventory_daily_source
    ON dbo.amazon_inventory_daily (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_sales_traffic_daily') AND name = 'IX_amazon_sales_traffic_daily_date')
    CREATE INDEX IX_amazon_sales_traffic_daily_date
    ON dbo.amazon_sales_traffic_daily (marketplace_id, report_date DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_sales_traffic_daily') AND name = 'IX_amazon_sales_traffic_daily_source')
    CREATE INDEX IX_amazon_sales_traffic_daily_source
    ON dbo.amazon_sales_traffic_daily (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_sales_traffic_asin_daily') AND name = 'IX_amazon_sales_traffic_asin_daily_key')
    CREATE INDEX IX_amazon_sales_traffic_asin_daily_key
    ON dbo.amazon_sales_traffic_asin_daily (marketplace_id, report_start_date DESC, report_end_date DESC, parent_asin, child_asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_sales_traffic_asin_daily') AND name = 'IX_amazon_sales_traffic_asin_daily_source')
    CREATE INDEX IX_amazon_sales_traffic_asin_daily_source
    ON dbo.amazon_sales_traffic_asin_daily (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_settlement_transaction') AND name = 'IX_amazon_settlement_transaction_settlement')
    CREATE INDEX IX_amazon_settlement_transaction_settlement
    ON dbo.amazon_settlement_transaction (marketplace_id, settlement_id, is_settlement_summary, transaction_type);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_settlement_transaction') AND name = 'IX_amazon_settlement_transaction_order_sku')
    CREATE INDEX IX_amazon_settlement_transaction_order_sku
    ON dbo.amazon_settlement_transaction (marketplace_id, order_id, seller_sku, amount_category, profit_bucket);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_settlement_transaction') AND name = 'IX_amazon_settlement_transaction_source')
    CREATE INDEX IX_amazon_settlement_transaction_source
    ON dbo.amazon_settlement_transaction (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_order_item') AND name = 'IX_amazon_order_item_order_sku')
    CREATE INDEX IX_amazon_order_item_order_sku
    ON dbo.amazon_order_item (marketplace_id, amazon_order_id, seller_sku, asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_order_item') AND name = 'IX_amazon_order_item_source')
    CREATE INDEX IX_amazon_order_item_source
    ON dbo.amazon_order_item (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_fba_reimbursement') AND name = 'IX_amazon_fba_reimbursement_key')
    CREATE INDEX IX_amazon_fba_reimbursement_key
    ON dbo.amazon_fba_reimbursement (marketplace_id, reimbursement_id, case_id, seller_sku, asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_fba_reimbursement') AND name = 'IX_amazon_fba_reimbursement_source')
    CREATE INDEX IX_amazon_fba_reimbursement_source
    ON dbo.amazon_fba_reimbursement (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_fba_fee_preview') AND name = 'IX_amazon_fba_fee_preview_sku')
    CREATE INDEX IX_amazon_fba_fee_preview_sku
    ON dbo.amazon_fba_fee_preview (marketplace_id, seller_sku, fnsku, asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_fba_fee_preview') AND name = 'IX_amazon_fba_fee_preview_source')
    CREATE INDEX IX_amazon_fba_fee_preview_source
    ON dbo.amazon_fba_fee_preview (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_inventory_ledger_summary_daily') AND name = 'IX_amazon_inventory_ledger_summary_daily_key')
    CREATE INDEX IX_amazon_inventory_ledger_summary_daily_key
    ON dbo.amazon_inventory_ledger_summary_daily (marketplace_id, seller_sku, fnsku, asin, ledger_date_raw);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_inventory_ledger_detail') AND name = 'IX_amazon_inventory_ledger_detail_key')
    CREATE INDEX IX_amazon_inventory_ledger_detail_key
    ON dbo.amazon_inventory_ledger_detail (marketplace_id, seller_sku, fnsku, asin, event_type, reference_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_reserved_inventory_daily') AND name = 'IX_amazon_reserved_inventory_daily_key')
    CREATE INDEX IX_amazon_reserved_inventory_daily_key
    ON dbo.amazon_reserved_inventory_daily (marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_inventory_planning_daily') AND name = 'IX_amazon_inventory_planning_daily_key')
    CREATE INDEX IX_amazon_inventory_planning_daily_key
    ON dbo.amazon_inventory_planning_daily (marketplace_id, seller_sku, fnsku, asin, snapshot_date_raw);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_promotion_performance') AND name = 'IX_amazon_promotion_performance_key')
    CREATE INDEX IX_amazon_promotion_performance_key
    ON dbo.amazon_promotion_performance (marketplace_id, promotion_id, status);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_promotion_product_performance') AND name = 'IX_amazon_promotion_product_performance_key')
    CREATE INDEX IX_amazon_promotion_product_performance_key
    ON dbo.amazon_promotion_product_performance (marketplace_id, promotion_id, asin);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_coupon_performance') AND name = 'IX_amazon_coupon_performance_key')
    CREATE INDEX IX_amazon_coupon_performance_key
    ON dbo.amazon_coupon_performance (marketplace_id, coupon_id, merchant_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_coupon_asin') AND name = 'IX_amazon_coupon_asin_key')
    CREATE INDEX IX_amazon_coupon_asin_key
    ON dbo.amazon_coupon_asin (marketplace_id, coupon_id, asin);
GO


/* =========================================================
   Amazon Ads indexes
   ========================================================= */

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_profile') AND name = 'UX_amazon_ads_profile_profile_id')
    CREATE UNIQUE INDEX UX_amazon_ads_profile_profile_id
    ON dbo.amazon_ads_profile (profile_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_profile') AND name = 'IX_amazon_ads_profile_marketplace')
    CREATE INDEX IX_amazon_ads_profile_marketplace
    ON dbo.amazon_ads_profile (marketplace_id, country_code, account_type);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_campaign_daily') AND name = 'IX_amazon_ads_sp_campaign_daily_key')
    CREATE INDEX IX_amazon_ads_sp_campaign_daily_key
    ON dbo.amazon_ads_sp_campaign_daily (profile_id, report_date DESC, campaign_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_campaign_daily') AND name = 'UX_amazon_ads_sp_campaign_daily_business_key')
    CREATE UNIQUE INDEX UX_amazon_ads_sp_campaign_daily_business_key
    ON dbo.amazon_ads_sp_campaign_daily (business_key_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_campaign_daily') AND name = 'IX_amazon_ads_sp_campaign_daily_source')
    CREATE INDEX IX_amazon_ads_sp_campaign_daily_source
    ON dbo.amazon_ads_sp_campaign_daily (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_targeting_daily') AND name = 'IX_amazon_ads_sp_targeting_daily_key')
    CREATE INDEX IX_amazon_ads_sp_targeting_daily_key
    ON dbo.amazon_ads_sp_targeting_daily (profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_targeting_daily') AND name = 'UX_amazon_ads_sp_targeting_daily_business_key')
    CREATE UNIQUE INDEX UX_amazon_ads_sp_targeting_daily_business_key
    ON dbo.amazon_ads_sp_targeting_daily (business_key_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_targeting_daily') AND name = 'IX_amazon_ads_sp_targeting_daily_source')
    CREATE INDEX IX_amazon_ads_sp_targeting_daily_source
    ON dbo.amazon_ads_sp_targeting_daily (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_search_term_daily') AND name = 'IX_amazon_ads_sp_search_term_daily_key')
    CREATE INDEX IX_amazon_ads_sp_search_term_daily_key
    ON dbo.amazon_ads_sp_search_term_daily (profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_search_term_daily') AND name = 'UX_amazon_ads_sp_search_term_daily_business_key')
    CREATE UNIQUE INDEX UX_amazon_ads_sp_search_term_daily_business_key
    ON dbo.amazon_ads_sp_search_term_daily (business_key_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_search_term_daily') AND name = 'IX_amazon_ads_sp_search_term_daily_source')
    CREATE INDEX IX_amazon_ads_sp_search_term_daily_source
    ON dbo.amazon_ads_sp_search_term_daily (source_report_id, source_row_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_advertised_product_daily') AND name = 'IX_amazon_ads_sp_advertised_product_daily_key')
    CREATE INDEX IX_amazon_ads_sp_advertised_product_daily_key
    ON dbo.amazon_ads_sp_advertised_product_daily (profile_id, report_date DESC, advertised_asin, advertised_sku);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_advertised_product_daily') AND name = 'UX_amazon_ads_sp_advertised_product_daily_business_key')
    CREATE UNIQUE INDEX UX_amazon_ads_sp_advertised_product_daily_business_key
    ON dbo.amazon_ads_sp_advertised_product_daily (business_key_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_advertised_product_daily') AND name = 'IX_amazon_ads_sp_advertised_product_daily_campaign')
    CREATE INDEX IX_amazon_ads_sp_advertised_product_daily_campaign
    ON dbo.amazon_ads_sp_advertised_product_daily (profile_id, campaign_id, ad_group_id, report_date DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.amazon_ads_sp_advertised_product_daily') AND name = 'IX_amazon_ads_sp_advertised_product_daily_source')
    CREATE INDEX IX_amazon_ads_sp_advertised_product_daily_source
    ON dbo.amazon_ads_sp_advertised_product_daily (source_report_id, source_row_hash);
GO

