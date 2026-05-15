-- SellerDataPipeline initial Azure SQL schema.
-- Version: v1.14 Ads repository/upsert ready draft
-- Status: NOT executed yet. Review manually before running against Azure SQL.
-- Scope:
--   1) Control / raw archive / field catalog tables
--   2) First SP-API normalized tables based on sampled reports
--   3) First Amazon Ads normalized tables based on confirmed SP canary samples
--   4) Schema validation events for raw-file/table drift review

/* =========================================================
   L0: marketplace and task audit / sync run log
   ========================================================= */

IF OBJECT_ID('dbo.amazon_marketplace', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_marketplace (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_marketplace PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        marketplace_name NVARCHAR(200) NOT NULL,
        country_code NVARCHAR(10) NOT NULL,
        currency NVARCHAR(10) NOT NULL,
        region NVARCHAR(20) NOT NULL,
        endpoint NVARCHAR(300) NOT NULL,
        is_active BIT NOT NULL CONSTRAINT DF_amazon_marketplace_is_active DEFAULT 1,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_marketplace_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_marketplace_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_sync_run_log', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_sync_run_log (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_sync_run_log PRIMARY KEY,
        workflow_name NVARCHAR(120) NULL,
        job_name NVARCHAR(120) NOT NULL,
        task_type NVARCHAR(80) NULL,
        trigger_type NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_sync_run_log_trigger_type DEFAULT 'manual',
        run_mode NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_sync_run_log_run_mode DEFAULT 'local',
        parent_run_id BIGINT NULL,
        job_execution_id NVARCHAR(200) NULL,
        marketplace_id NVARCHAR(50) NULL,
        source_system NVARCHAR(50) NULL,
        status NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_sync_run_log_status DEFAULT 'running',
        started_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_sync_run_log_started_at DEFAULT SYSUTCDATETIME(),
        finished_at DATETIME2 NULL,
        duration_ms BIGINT NULL,
        date_start DATE NULL,
        date_end DATE NULL,
        rows_read INT NOT NULL CONSTRAINT DF_amazon_sync_run_log_rows_read DEFAULT 0,
        rows_written INT NOT NULL CONSTRAINT DF_amazon_sync_run_log_rows_written DEFAULT 0,
        rows_skipped INT NOT NULL CONSTRAINT DF_amazon_sync_run_log_rows_skipped DEFAULT 0,
        rows_failed INT NOT NULL CONSTRAINT DF_amazon_sync_run_log_rows_failed DEFAULT 0,
        files_created INT NOT NULL CONSTRAINT DF_amazon_sync_run_log_files_created DEFAULT 0,
        retry_count INT NOT NULL CONSTRAINT DF_amazon_sync_run_log_retry_count DEFAULT 0,
        config_snapshot_json NVARCHAR(MAX) NULL,
        message NVARCHAR(MAX) NULL,
        error_type NVARCHAR(200) NULL,
        error_detail NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_sync_run_log_created_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

/* =========================================================
   L0/L1: report request and raw file archive
   ========================================================= */

IF OBJECT_ID('dbo.amazon_report_request', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_report_request (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_report_request PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        source_system NVARCHAR(50) NOT NULL,
        report_type NVARCHAR(120) NOT NULL,
        report_options_json NVARCHAR(MAX) NULL,
        data_start_time DATETIME2 NULL,
        data_end_time DATETIME2 NULL,
        report_id NVARCHAR(120) NULL,
        report_document_id NVARCHAR(120) NULL,
        processing_status NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_report_request_processing_status DEFAULT 'SUBMITTED',
        download_status NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_report_request_download_status DEFAULT 'PENDING',
        parse_status NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_report_request_parse_status DEFAULT 'PENDING',
        requested_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_report_request_requested_at DEFAULT SYSUTCDATETIME(),
        last_checked_at DATETIME2 NULL,
        completed_at DATETIME2 NULL,
        downloaded_at DATETIME2 NULL,
        parsed_at DATETIME2 NULL,
        retry_count INT NOT NULL CONSTRAINT DF_amazon_report_request_retry_count DEFAULT 0,
        source_run_id BIGINT NULL,
        error_message NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_report_request_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_report_request_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_raw_report_file', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_raw_report_file (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_raw_report_file PRIMARY KEY,
        report_request_id BIGINT NULL,
        marketplace_id NVARCHAR(50) NOT NULL,
        source_system NVARCHAR(50) NOT NULL,
        report_type NVARCHAR(120) NOT NULL,
        report_id NVARCHAR(120) NULL,
        report_document_id NVARCHAR(120) NULL,
        file_role NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_raw_report_file_file_role DEFAULT 'raw',
        storage_backend NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_raw_report_file_storage_backend DEFAULT 'local',
        file_path NVARCHAR(700) NOT NULL,
        file_name NVARCHAR(300) NOT NULL,
        file_extension NVARCHAR(30) NULL,
        content_type NVARCHAR(200) NULL,
        compression_algorithm NVARCHAR(50) NULL,
        encoding NVARCHAR(80) NULL,
        delimiter NVARCHAR(20) NULL,
        row_count INT NULL,
        column_count INT NULL,
        sha256 NVARCHAR(100) NULL,
        byte_size BIGINT NULL,
        downloaded_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_raw_report_file_downloaded_at DEFAULT SYSUTCDATETIME(),
        source_run_id BIGINT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_raw_report_file_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_raw_report_file_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_report_field_catalog', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_report_field_catalog (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_report_field_catalog PRIMARY KEY,
        source_system NVARCHAR(50) NOT NULL,
        report_type NVARCHAR(120) NOT NULL,
        marketplace_id NVARCHAR(50) NULL,
        sample_file_id BIGINT NULL,
        field_position INT NULL,
        source_field_name NVARCHAR(300) NOT NULL,
        normalized_field_name NVARCHAR(200) NULL,
        target_table NVARCHAR(200) NULL,
        target_column NVARCHAR(200) NULL,
        data_type_suggestion NVARCHAR(100) NULL,
        nullable_observed BIT NULL,
        sample_values_json NVARCHAR(MAX) NULL,
        field_status NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_report_field_catalog_field_status DEFAULT 'observed',
        notes NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_report_field_catalog_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_report_field_catalog_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_schema_validation_event', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_schema_validation_event (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_schema_validation_event PRIMARY KEY,
        source_system NVARCHAR(50) NOT NULL,
        marketplace_id NVARCHAR(50) NULL,
        report_type NVARCHAR(120) NOT NULL,
        report_id NVARCHAR(120) NULL,
        raw_file_id BIGINT NULL,
        raw_file_path NVARCHAR(1000) NULL,
        validation_stage NVARCHAR(80) NOT NULL CONSTRAINT DF_amazon_schema_validation_event_stage DEFAULT 'post_download',
        validation_status NVARCHAR(80) NOT NULL,
        severity NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_schema_validation_event_severity DEFAULT 'info',
        row_count INT NULL,
        observed_fields_json NVARCHAR(MAX) NULL,
        expected_fields_json NVARCHAR(MAX) NULL,
        missing_fields_json NVARCHAR(MAX) NULL,
        new_fields_json NVARCHAR(MAX) NULL,
        unmapped_fields_json NVARCHAR(MAX) NULL,
        requires_review BIT NOT NULL CONSTRAINT DF_amazon_schema_validation_event_requires_review DEFAULT 0,
        notification_status NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_schema_validation_event_notification_status DEFAULT 'not_required',
        notified_at DATETIME2 NULL,
        message NVARCHAR(MAX) NULL,
        source_run_id BIGINT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_schema_validation_event_created_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_sku_cost', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_sku_cost (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_sku_cost PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        seller_sku NVARCHAR(200) NOT NULL,
        asin NVARCHAR(50) NULL,
        product_cost DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_sku_cost_product_cost DEFAULT 0,
        first_mile_cost DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_sku_cost_first_mile_cost DEFAULT 0,
        packaging_cost DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_sku_cost_packaging_cost DEFAULT 0,
        other_unit_cost DECIMAL(18,4) NOT NULL CONSTRAINT DF_amazon_sku_cost_other_unit_cost DEFAULT 0,
        currency NVARCHAR(10) NOT NULL,
        effective_from DATE NOT NULL,
        effective_to DATE NULL,
        remark NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_sku_cost_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_sku_cost_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

/* =========================================================
   L3: listing, inventory, sales and traffic
   ========================================================= */

IF OBJECT_ID('dbo.amazon_listing_snapshot', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_listing_snapshot (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_listing_snapshot PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        snapshot_date DATE NOT NULL,
        listing_id NVARCHAR(200) NOT NULL,
        seller_sku NVARCHAR(200) NOT NULL,
        asin NVARCHAR(50) NULL,
        product_id NVARCHAR(100) NULL,
        product_id_type NVARCHAR(50) NULL,
        item_name NVARCHAR(1000) NULL,
        item_description NVARCHAR(MAX) NULL,
        price DECIMAL(18,4) NULL,
        currency NVARCHAR(10) NULL,
        quantity INT NULL,
        pending_quantity INT NULL,
        open_date_raw NVARCHAR(100) NULL,
        open_date_utc DATETIME2 NULL,
        item_is_marketplace BIT NULL,
        item_condition NVARCHAR(50) NULL,
        fulfillment_channel NVARCHAR(100) NULL,
        merchant_shipping_group NVARCHAR(200) NULL,
        status NVARCHAR(50) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_listing_snapshot_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_listing_snapshot_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_listing_snapshot_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_inventory_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_inventory_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_inventory_daily PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        snapshot_date DATE NOT NULL,
        seller_sku NVARCHAR(200) NOT NULL,
        fnsku NVARCHAR(100) NULL,
        asin NVARCHAR(50) NULL,
        product_name NVARCHAR(1000) NULL,
        condition NVARCHAR(50) NULL,
        your_price DECIMAL(18,4) NULL,
        currency NVARCHAR(10) NULL,
        mfn_listing_exists BIT NULL,
        mfn_fulfillable_quantity INT NULL,
        afn_listing_exists BIT NULL,
        afn_warehouse_quantity INT NULL,
        afn_fulfillable_quantity INT NULL,
        afn_unsellable_quantity INT NULL,
        afn_reserved_quantity INT NULL,
        afn_total_quantity INT NULL,
        per_unit_volume DECIMAL(18,6) NULL,
        afn_inbound_working_quantity INT NULL,
        afn_inbound_shipped_quantity INT NULL,
        afn_inbound_receiving_quantity INT NULL,
        afn_researching_quantity INT NULL,
        afn_reserved_future_supply INT NULL,
        afn_future_supply_buyable INT NULL,
        store NVARCHAR(200) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_inventory_daily_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_inventory_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_inventory_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_sales_traffic_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_sales_traffic_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_sales_traffic_daily PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        report_date DATE NOT NULL,
        date_granularity NVARCHAR(50) NULL,
        asin_granularity NVARCHAR(50) NULL,
        ordered_product_sales_amount DECIMAL(18,4) NULL,
        ordered_product_sales_currency NVARCHAR(10) NULL,
        ordered_product_sales_b2b_amount DECIMAL(18,4) NULL,
        ordered_product_sales_b2b_currency NVARCHAR(10) NULL,
        average_sales_per_order_item_amount DECIMAL(18,4) NULL,
        average_sales_per_order_item_currency NVARCHAR(10) NULL,
        average_sales_per_order_item_b2b_amount DECIMAL(18,4) NULL,
        average_sales_per_order_item_b2b_currency NVARCHAR(10) NULL,
        average_units_per_order_item DECIMAL(18,6) NULL,
        average_units_per_order_item_b2b DECIMAL(18,6) NULL,
        average_selling_price_amount DECIMAL(18,4) NULL,
        average_selling_price_currency NVARCHAR(10) NULL,
        average_selling_price_b2b_amount DECIMAL(18,4) NULL,
        average_selling_price_b2b_currency NVARCHAR(10) NULL,
        units_ordered INT NULL,
        units_ordered_b2b INT NULL,
        total_order_items INT NULL,
        total_order_items_b2b INT NULL,
        units_refunded INT NULL,
        refund_rate DECIMAL(18,6) NULL,
        claims_granted INT NULL,
        claims_amount DECIMAL(18,4) NULL,
        claims_amount_currency NVARCHAR(10) NULL,
        shipped_product_sales_amount DECIMAL(18,4) NULL,
        shipped_product_sales_currency NVARCHAR(10) NULL,
        units_shipped INT NULL,
        orders_shipped INT NULL,
        browser_page_views INT NULL,
        mobile_app_page_views INT NULL,
        page_views INT NULL,
        browser_sessions INT NULL,
        mobile_app_sessions INT NULL,
        sessions INT NULL,
        buy_box_percentage DECIMAL(18,6) NULL,
        order_item_session_percentage DECIMAL(18,6) NULL,
        unit_session_percentage DECIMAL(18,6) NULL,
        average_offer_count DECIMAL(18,6) NULL,
        average_parent_items DECIMAL(18,6) NULL,
        feedback_received INT NULL,
        negative_feedback_received INT NULL,
        received_negative_feedback_rate DECIMAL(18,6) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_sales_traffic_daily_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_sales_traffic_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_sales_traffic_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_sales_traffic_asin_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_sales_traffic_asin_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_sales_traffic_asin_daily PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        report_start_date DATE NULL,
        report_end_date DATE NULL,
        parent_asin NVARCHAR(50) NULL,
        child_asin NVARCHAR(50) NULL,
        date_granularity NVARCHAR(50) NULL,
        asin_granularity NVARCHAR(50) NULL,
        ordered_product_sales_amount DECIMAL(18,4) NULL,
        ordered_product_sales_currency NVARCHAR(10) NULL,
        ordered_product_sales_b2b_amount DECIMAL(18,4) NULL,
        ordered_product_sales_b2b_currency NVARCHAR(10) NULL,
        units_ordered INT NULL,
        units_ordered_b2b INT NULL,
        total_order_items INT NULL,
        total_order_items_b2b INT NULL,
        browser_page_views INT NULL,
        browser_page_views_b2b INT NULL,
        browser_page_views_percentage DECIMAL(18,6) NULL,
        browser_page_views_percentage_b2b DECIMAL(18,6) NULL,
        mobile_app_page_views INT NULL,
        mobile_app_page_views_b2b INT NULL,
        mobile_app_page_views_percentage DECIMAL(18,6) NULL,
        mobile_app_page_views_percentage_b2b DECIMAL(18,6) NULL,
        page_views INT NULL,
        page_views_b2b INT NULL,
        page_views_percentage DECIMAL(18,6) NULL,
        page_views_percentage_b2b DECIMAL(18,6) NULL,
        browser_sessions INT NULL,
        browser_sessions_b2b INT NULL,
        browser_session_percentage DECIMAL(18,6) NULL,
        browser_session_percentage_b2b DECIMAL(18,6) NULL,
        mobile_app_sessions INT NULL,
        mobile_app_sessions_b2b INT NULL,
        mobile_app_session_percentage DECIMAL(18,6) NULL,
        mobile_app_session_percentage_b2b DECIMAL(18,6) NULL,
        sessions INT NULL,
        sessions_b2b INT NULL,
        session_percentage DECIMAL(18,6) NULL,
        session_percentage_b2b DECIMAL(18,6) NULL,
        buy_box_percentage DECIMAL(18,6) NULL,
        buy_box_percentage_b2b DECIMAL(18,6) NULL,
        unit_session_percentage DECIMAL(18,6) NULL,
        unit_session_percentage_b2b DECIMAL(18,6) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_sales_traffic_asin_daily_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_sales_traffic_asin_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_sales_traffic_asin_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

/* =========================================================
   L3: finance, orders, reimbursements and fee preview
   ========================================================= */

IF OBJECT_ID('dbo.amazon_settlement_transaction', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_settlement_transaction (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_settlement_transaction PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        settlement_id NVARCHAR(200) NULL,
        settlement_start_date_raw NVARCHAR(100) NULL,
        settlement_end_date_raw NVARCHAR(100) NULL,
        deposit_date_raw NVARCHAR(100) NULL,
        total_amount DECIMAL(18,4) NULL,
        currency NVARCHAR(10) NULL,
        is_settlement_summary BIT NOT NULL CONSTRAINT DF_amazon_settlement_transaction_is_summary DEFAULT 0,
        transaction_type NVARCHAR(120) NULL,
        order_id NVARCHAR(200) NULL,
        merchant_order_id NVARCHAR(200) NULL,
        adjustment_id NVARCHAR(200) NULL,
        shipment_id NVARCHAR(200) NULL,
        marketplace_name NVARCHAR(200) NULL,
        amount_type NVARCHAR(120) NULL,
        amount_description NVARCHAR(300) NULL,
        amount DECIMAL(18,4) NULL,
        amount_category NVARCHAR(120) NOT NULL,
        profit_bucket NVARCHAR(120) NOT NULL,
        fulfillment_id NVARCHAR(100) NULL,
        posted_date_raw NVARCHAR(100) NULL,
        posted_date_time_raw NVARCHAR(100) NULL,
        order_item_code NVARCHAR(200) NULL,
        merchant_order_item_id NVARCHAR(200) NULL,
        merchant_adjustment_item_id NVARCHAR(200) NULL,
        seller_sku NVARCHAR(200) NULL,
        quantity_purchased INT NULL,
        promotion_id NVARCHAR(500) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_settlement_transaction_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_settlement_transaction_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_settlement_transaction_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_order_item', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_order_item (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_order_item PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        amazon_order_id NVARCHAR(200) NULL,
        merchant_order_id NVARCHAR(200) NULL,
        purchase_date_raw NVARCHAR(100) NULL,
        last_updated_date_raw NVARCHAR(100) NULL,
        order_status NVARCHAR(100) NULL,
        fulfillment_channel NVARCHAR(100) NULL,
        sales_channel NVARCHAR(100) NULL,
        order_channel NVARCHAR(100) NULL,
        ship_service_level NVARCHAR(100) NULL,
        product_name NVARCHAR(1000) NULL,
        seller_sku NVARCHAR(200) NULL,
        asin NVARCHAR(50) NULL,
        item_status NVARCHAR(100) NULL,
        quantity INT NULL,
        currency NVARCHAR(10) NULL,
        item_price DECIMAL(18,4) NULL,
        item_tax DECIMAL(18,4) NULL,
        shipping_price DECIMAL(18,4) NULL,
        shipping_tax DECIMAL(18,4) NULL,
        gift_wrap_price DECIMAL(18,4) NULL,
        gift_wrap_tax DECIMAL(18,4) NULL,
        item_promotion_discount DECIMAL(18,4) NULL,
        ship_promotion_discount DECIMAL(18,4) NULL,
        ship_city NVARCHAR(200) NULL,
        ship_state NVARCHAR(100) NULL,
        ship_postal_code NVARCHAR(50) NULL,
        ship_country NVARCHAR(50) NULL,
        promotion_ids NVARCHAR(1000) NULL,
        is_business_order BIT NULL,
        purchase_order_number NVARCHAR(200) NULL,
        price_designation NVARCHAR(100) NULL,
        signature_confirmation_recommended BIT NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_order_item_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_order_item_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_order_item_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_fba_reimbursement', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_fba_reimbursement (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_fba_reimbursement PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        approval_date_raw NVARCHAR(100) NULL,
        reimbursement_id NVARCHAR(200) NULL,
        case_id NVARCHAR(200) NULL,
        amazon_order_id NVARCHAR(200) NULL,
        reason NVARCHAR(300) NULL,
        seller_sku NVARCHAR(200) NULL,
        fnsku NVARCHAR(100) NULL,
        asin NVARCHAR(50) NULL,
        product_name NVARCHAR(1000) NULL,
        condition NVARCHAR(50) NULL,
        currency NVARCHAR(10) NULL,
        amount_per_unit DECIMAL(18,4) NULL,
        amount_total DECIMAL(18,4) NULL,
        quantity_reimbursed_cash INT NULL,
        quantity_reimbursed_inventory INT NULL,
        quantity_reimbursed_total INT NULL,
        original_reimbursement_id NVARCHAR(200) NULL,
        original_reimbursement_type NVARCHAR(100) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_fba_reimbursement_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_fba_reimbursement_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_fba_reimbursement_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_fba_fee_preview', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_fba_fee_preview (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_fba_fee_preview PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        seller_sku NVARCHAR(200) NULL,
        fnsku NVARCHAR(100) NULL,
        asin NVARCHAR(50) NULL,
        amazon_store NVARCHAR(200) NULL,
        product_name NVARCHAR(1000) NULL,
        product_group NVARCHAR(200) NULL,
        brand NVARCHAR(200) NULL,
        fulfilled_by NVARCHAR(100) NULL,
        your_price DECIMAL(18,4) NULL,
        sales_price DECIMAL(18,4) NULL,
        longest_side DECIMAL(18,6) NULL,
        median_side DECIMAL(18,6) NULL,
        shortest_side DECIMAL(18,6) NULL,
        length_and_girth DECIMAL(18,6) NULL,
        unit_of_dimension NVARCHAR(50) NULL,
        item_package_weight DECIMAL(18,6) NULL,
        unit_of_weight NVARCHAR(50) NULL,
        product_size_tier NVARCHAR(200) NULL,
        currency NVARCHAR(10) NULL,
        estimated_fee_total DECIMAL(18,4) NULL,
        estimated_referral_fee_per_unit DECIMAL(18,4) NULL,
        estimated_variable_closing_fee DECIMAL(18,4) NULL,
        estimated_order_handling_fee_per_order DECIMAL(18,4) NULL,
        estimated_pick_pack_fee_per_unit DECIMAL(18,4) NULL,
        estimated_weight_handling_fee_per_unit DECIMAL(18,4) NULL,
        expected_fulfillment_fee_per_unit DECIMAL(18,4) NULL,
        estimated_future_fee_total DECIMAL(18,4) NULL,
        estimated_future_order_handling_fee_per_order DECIMAL(18,4) NULL,
        estimated_future_pick_pack_fee_per_unit DECIMAL(18,4) NULL,
        estimated_future_weight_handling_fee_per_unit DECIMAL(18,4) NULL,
        expected_future_fulfillment_fee_per_unit DECIMAL(18,4) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_fba_fee_preview_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_fba_fee_preview_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_fba_fee_preview_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

/* =========================================================
   L3: inventory planning, ledger and reserved inventory
   ========================================================= */

IF OBJECT_ID('dbo.amazon_inventory_ledger_summary_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_inventory_ledger_summary_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_inventory_ledger_summary_daily PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        ledger_date_raw NVARCHAR(100) NULL,
        fnsku NVARCHAR(100) NULL,
        asin NVARCHAR(50) NULL,
        seller_sku NVARCHAR(200) NULL,
        title NVARCHAR(1000) NULL,
        disposition NVARCHAR(100) NULL,
        starting_warehouse_balance INT NULL,
        in_transit_between_warehouses INT NULL,
        receipts INT NULL,
        customer_shipments INT NULL,
        customer_returns INT NULL,
        vendor_returns INT NULL,
        warehouse_transfer_in_out INT NULL,
        found INT NULL,
        lost INT NULL,
        damaged INT NULL,
        disposed INT NULL,
        other_events INT NULL,
        ending_warehouse_balance INT NULL,
        unknown_events INT NULL,
        location NVARCHAR(100) NULL,
        store NVARCHAR(200) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_inventory_ledger_summary_daily_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_inventory_ledger_summary_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_inventory_ledger_summary_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_inventory_ledger_detail', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_inventory_ledger_detail (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_inventory_ledger_detail PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        ledger_date_raw NVARCHAR(100) NULL,
        fnsku NVARCHAR(100) NULL,
        asin NVARCHAR(50) NULL,
        seller_sku NVARCHAR(200) NULL,
        title NVARCHAR(1000) NULL,
        event_type NVARCHAR(200) NULL,
        reference_id NVARCHAR(300) NULL,
        quantity INT NULL,
        fulfillment_center NVARCHAR(100) NULL,
        disposition NVARCHAR(100) NULL,
        reason NVARCHAR(300) NULL,
        country NVARCHAR(50) NULL,
        reconciled_quantity INT NULL,
        unreconciled_quantity INT NULL,
        date_time_raw NVARCHAR(100) NULL,
        store NVARCHAR(200) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_inventory_ledger_detail_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_inventory_ledger_detail_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_inventory_ledger_detail_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_reserved_inventory_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_reserved_inventory_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_reserved_inventory_daily PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        snapshot_date DATE NOT NULL CONSTRAINT DF_amazon_reserved_inventory_daily_snapshot_date DEFAULT CONVERT(date, SYSUTCDATETIME()),
        seller_sku NVARCHAR(200) NULL,
        fnsku NVARCHAR(100) NULL,
        asin NVARCHAR(50) NULL,
        product_name NVARCHAR(1000) NULL,
        reserved_quantity INT NULL,
        reserved_customer_orders INT NULL,
        reserved_fc_transfers INT NULL,
        reserved_fc_processing INT NULL,
        program NVARCHAR(100) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_reserved_inventory_daily_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_reserved_inventory_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_reserved_inventory_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_inventory_planning_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_inventory_planning_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_inventory_planning_daily PRIMARY KEY,
        marketplace_id NVARCHAR(50) NOT NULL,
        snapshot_date_raw NVARCHAR(100) NULL,
        seller_sku NVARCHAR(200) NULL,
        fnsku NVARCHAR(100) NULL,
        asin NVARCHAR(50) NULL,
        product_name NVARCHAR(1000) NULL,
        condition NVARCHAR(50) NULL,
        available_quantity INT NULL,
        pending_removal_quantity INT NULL,
        inv_age_0_to_90_days INT NULL,
        inv_age_91_to_180_days INT NULL,
        inv_age_181_to_270_days INT NULL,
        inv_age_271_to_365_days INT NULL,
        inv_age_366_to_455_days INT NULL,
        inv_age_456_plus_days INT NULL,
        currency NVARCHAR(10) NULL,
        units_shipped_t7 INT NULL,
        units_shipped_t30 INT NULL,
        units_shipped_t60 INT NULL,
        units_shipped_t90 INT NULL,
        alert NVARCHAR(300) NULL,
        your_price DECIMAL(18,4) NULL,
        sales_price DECIMAL(18,4) NULL,
        recommended_action NVARCHAR(500) NULL,
        recommended_sales_price DECIMAL(18,4) NULL,
        recommended_sale_duration_days INT NULL,
        recommended_removal_quantity INT NULL,
        estimated_cost_savings_of_recommended_actions DECIMAL(18,4) NULL,
        sell_through DECIMAL(18,6) NULL,
        item_volume DECIMAL(18,6) NULL,
        volume_unit_measurement NVARCHAR(50) NULL,
        storage_type NVARCHAR(100) NULL,
        storage_volume DECIMAL(18,6) NULL,
        marketplace_name NVARCHAR(200) NULL,
        product_group NVARCHAR(200) NULL,
        sales_rank INT NULL,
        days_of_supply DECIMAL(18,6) NULL,
        estimated_excess_quantity INT NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_inventory_planning_daily_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_inventory_planning_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_inventory_planning_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

/* =========================================================
   L3: promotion and coupon performance
   ========================================================= */

IF OBJECT_ID('dbo.amazon_promotion_performance', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_promotion_performance (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_promotion_performance PRIMARY KEY,
        marketplace_id NVARCHAR(50) NULL,
        promotion_id NVARCHAR(200) NULL,
        merchant_id NVARCHAR(200) NULL,
        promotion_name NVARCHAR(500) NULL,
        promotion_type NVARCHAR(100) NULL,
        status NVARCHAR(100) NULL,
        glance_views INT NULL,
        units_sold INT NULL,
        revenue DECIMAL(18,4) NULL,
        revenue_currency_code NVARCHAR(10) NULL,
        start_date_time_raw NVARCHAR(100) NULL,
        end_date_time_raw NVARCHAR(100) NULL,
        created_date_time_raw NVARCHAR(100) NULL,
        last_updated_date_time_raw NVARCHAR(100) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_promotion_performance_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_promotion_performance_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_promotion_performance_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_promotion_product_performance', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_promotion_product_performance (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_promotion_product_performance PRIMARY KEY,
        marketplace_id NVARCHAR(50) NULL,
        promotion_id NVARCHAR(200) NULL,
        merchant_id NVARCHAR(200) NULL,
        promotion_name NVARCHAR(500) NULL,
        promotion_type NVARCHAR(100) NULL,
        status NVARCHAR(100) NULL,
        asin NVARCHAR(50) NULL,
        product_name NVARCHAR(1000) NULL,
        product_glance_views INT NULL,
        product_units_sold INT NULL,
        product_revenue DECIMAL(18,4) NULL,
        product_revenue_currency_code NVARCHAR(10) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_promotion_product_performance_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_promotion_product_performance_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_promotion_product_performance_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_coupon_performance', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_coupon_performance (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_coupon_performance PRIMARY KEY,
        marketplace_id NVARCHAR(50) NULL,
        coupon_id NVARCHAR(200) NULL,
        merchant_id NVARCHAR(200) NULL,
        currency_code NVARCHAR(10) NULL,
        name NVARCHAR(500) NULL,
        website_message NVARCHAR(1000) NULL,
        start_date_time_raw NVARCHAR(100) NULL,
        end_date_time_raw NVARCHAR(100) NULL,
        discount_type NVARCHAR(100) NULL,
        discount_amount DECIMAL(18,4) NULL,
        total_discount DECIMAL(18,4) NULL,
        clips INT NULL,
        redemptions INT NULL,
        budget DECIMAL(18,4) NULL,
        budget_spent DECIMAL(18,4) NULL,
        budget_remaining DECIMAL(18,4) NULL,
        budget_percentage_used DECIMAL(18,6) NULL,
        sales DECIMAL(18,4) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_coupon_performance_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_coupon_performance_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_coupon_performance_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_coupon_asin', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_coupon_asin (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_coupon_asin PRIMARY KEY,
        marketplace_id NVARCHAR(50) NULL,
        coupon_id NVARCHAR(200) NULL,
        merchant_id NVARCHAR(200) NULL,
        asin NVARCHAR(50) NULL,
        coupon_name NVARCHAR(500) NULL,
        currency_code NVARCHAR(10) NULL,
        start_date_time_raw NVARCHAR(100) NULL,
        end_date_time_raw NVARCHAR(100) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_coupon_asin_source_system DEFAULT 'sp_api_reports',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_coupon_asin_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_coupon_asin_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO


/* =========================================================
   L3: Amazon Ads Sponsored Products performance
   ========================================================= */

IF OBJECT_ID('dbo.amazon_ads_profile', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_ads_profile (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_ads_profile PRIMARY KEY,
        profile_id NVARCHAR(100) NOT NULL,
        marketplace_id NVARCHAR(50) NULL,
        country_code NVARCHAR(10) NULL,
        currency_code NVARCHAR(10) NULL,
        timezone NVARCHAR(100) NULL,
        account_id NVARCHAR(100) NULL,
        account_type NVARCHAR(100) NULL,
        account_name NVARCHAR(500) NULL,
        valid_payment_method BIT NULL,
        daily_budget DECIMAL(18,4) NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_ads_profile_source_system DEFAULT 'amazon_ads',
        raw_data NVARCHAR(MAX) NOT NULL,
        discovered_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_profile_discovered_at DEFAULT SYSUTCDATETIME(),
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_profile_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_profile_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_ads_sp_campaign_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_ads_sp_campaign_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_ads_sp_campaign_daily PRIMARY KEY,
        profile_id NVARCHAR(100) NOT NULL,
        marketplace_id NVARCHAR(50) NULL,
        report_date DATE NOT NULL,
        campaign_id NVARCHAR(100) NULL,
        campaign_name NVARCHAR(500) NULL,
        campaign_status NVARCHAR(100) NULL,
        impressions INT NULL,
        clicks INT NULL,
        cost DECIMAL(18,4) NULL,
        sales_7d DECIMAL(18,4) NULL,
        purchases_7d INT NULL,
        units_sold_clicks_7d INT NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_ads_sp_campaign_daily_source_system DEFAULT 'amazon_ads',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_index INT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        business_key_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_sp_campaign_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_sp_campaign_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_ads_sp_targeting_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_ads_sp_targeting_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_ads_sp_targeting_daily PRIMARY KEY,
        profile_id NVARCHAR(100) NOT NULL,
        marketplace_id NVARCHAR(50) NULL,
        report_date DATE NOT NULL,
        campaign_id NVARCHAR(100) NULL,
        campaign_name NVARCHAR(500) NULL,
        ad_group_id NVARCHAR(100) NULL,
        ad_group_name NVARCHAR(500) NULL,
        keyword_id NVARCHAR(100) NULL,
        keyword NVARCHAR(500) NULL,
        match_type NVARCHAR(100) NULL,
        targeting NVARCHAR(1000) NULL,
        impressions INT NULL,
        clicks INT NULL,
        cost DECIMAL(18,4) NULL,
        sales_7d DECIMAL(18,4) NULL,
        purchases_7d INT NULL,
        units_sold_clicks_7d INT NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_ads_sp_targeting_daily_source_system DEFAULT 'amazon_ads',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_index INT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        business_key_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_sp_targeting_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_sp_targeting_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_ads_sp_search_term_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_ads_sp_search_term_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_ads_sp_search_term_daily PRIMARY KEY,
        profile_id NVARCHAR(100) NOT NULL,
        marketplace_id NVARCHAR(50) NULL,
        report_date DATE NOT NULL,
        campaign_id NVARCHAR(100) NULL,
        campaign_name NVARCHAR(500) NULL,
        ad_group_id NVARCHAR(100) NULL,
        ad_group_name NVARCHAR(500) NULL,
        keyword_id NVARCHAR(100) NULL,
        keyword NVARCHAR(500) NULL,
        match_type NVARCHAR(100) NULL,
        targeting NVARCHAR(1000) NULL,
        search_term NVARCHAR(1000) NULL,
        impressions INT NULL,
        clicks INT NULL,
        cost DECIMAL(18,4) NULL,
        sales_7d DECIMAL(18,4) NULL,
        purchases_7d INT NULL,
        units_sold_clicks_7d INT NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_ads_sp_search_term_daily_source_system DEFAULT 'amazon_ads',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_index INT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        business_key_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_sp_search_term_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_sp_search_term_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_ads_sp_advertised_product_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_ads_sp_advertised_product_daily (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_amazon_ads_sp_advertised_product_daily PRIMARY KEY,
        profile_id NVARCHAR(100) NOT NULL,
        marketplace_id NVARCHAR(50) NULL,
        report_date DATE NOT NULL,
        campaign_id NVARCHAR(100) NULL,
        campaign_name NVARCHAR(500) NULL,
        ad_group_id NVARCHAR(100) NULL,
        ad_group_name NVARCHAR(500) NULL,
        advertised_asin NVARCHAR(50) NULL,
        advertised_sku NVARCHAR(200) NULL,
        impressions INT NULL,
        clicks INT NULL,
        cost DECIMAL(18,4) NULL,
        sales_7d DECIMAL(18,4) NULL,
        purchases_7d INT NULL,
        units_sold_clicks_7d INT NULL,
        source_system NVARCHAR(50) NOT NULL CONSTRAINT DF_amazon_ads_sp_advertised_product_daily_source_system DEFAULT 'amazon_ads',
        source_report_type NVARCHAR(120) NOT NULL,
        source_report_id NVARCHAR(120) NULL,
        source_report_request_id BIGINT NULL,
        source_raw_file_id BIGINT NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_run_id BIGINT NULL,
        source_row_index INT NULL,
        source_row_hash NVARCHAR(100) NOT NULL,
        business_key_hash NVARCHAR(100) NOT NULL,
        raw_data NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_sp_advertised_product_daily_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_amazon_ads_sp_advertised_product_daily_updated_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

/* =========================================================
   Seed stable first marketplace row. This is safe before any
   production data exists and can be re-run idempotently.
   ========================================================= */

IF OBJECT_ID('dbo.amazon_marketplace', 'U') IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM dbo.amazon_marketplace WHERE marketplace_id = 'ATVPDKIKX0DER')
BEGIN
    INSERT INTO dbo.amazon_marketplace (
        marketplace_id,
        marketplace_name,
        country_code,
        currency,
        region,
        endpoint
    )
    VALUES (
        'ATVPDKIKX0DER',
        'Amazon.com',
        'US',
        'USD',
        'NA',
        'https://sellingpartnerapi-na.amazon.com'
    );
END;
GO
