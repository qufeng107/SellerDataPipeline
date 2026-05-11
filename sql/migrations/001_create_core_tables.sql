-- SellerDataPipeline core schema for Azure SQL Database.
-- This is an initial baseline and can be adjusted before production use.

IF OBJECT_ID('dbo.amazon_report_request', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_report_request (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        marketplace NVARCHAR(50) NOT NULL,
        report_type NVARCHAR(120) NOT NULL,
        data_start_time DATETIME2 NULL,
        data_end_time DATETIME2 NULL,
        report_id NVARCHAR(200) NULL,
        report_document_id NVARCHAR(200) NULL,
        processing_status NVARCHAR(50) NOT NULL DEFAULT 'SUBMITTED',
        submit_status NVARCHAR(50) NOT NULL DEFAULT 'SUBMITTED',
        download_status NVARCHAR(50) NULL,
        parse_status NVARCHAR(50) NULL,
        requested_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        last_checked_at DATETIME2 NULL,
        completed_at DATETIME2 NULL,
        downloaded_at DATETIME2 NULL,
        parsed_at DATETIME2 NULL,
        retry_count INT NOT NULL DEFAULT 0,
        error_message NVARCHAR(MAX) NULL,
        raw_file_path NVARCHAR(500) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_sync_run_log', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_sync_run_log (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        job_name NVARCHAR(120) NOT NULL,
        run_id NVARCHAR(200) NULL,
        started_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        finished_at DATETIME2 NULL,
        status NVARCHAR(50) NOT NULL DEFAULT 'RUNNING',
        date_start DATE NULL,
        date_end DATE NULL,
        message NVARCHAR(MAX) NULL,
        error_detail NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_sku_cost', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_sku_cost (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        marketplace NVARCHAR(50) NOT NULL,
        sku NVARCHAR(200) NOT NULL,
        asin NVARCHAR(50) NULL,
        product_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
        first_mile_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
        packaging_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
        other_unit_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
        currency NVARCHAR(10) NOT NULL,
        effective_from DATE NOT NULL,
        effective_to DATE NULL,
        remark NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_sales_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_sales_daily (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        marketplace NVARCHAR(50) NOT NULL,
        sales_date DATE NOT NULL,
        sku NVARCHAR(200) NULL,
        asin NVARCHAR(50) NULL,
        ordered_units INT NOT NULL DEFAULT 0,
        orders_count INT NOT NULL DEFAULT 0,
        ordered_product_sales DECIMAL(18,4) NOT NULL DEFAULT 0,
        sessions INT NULL,
        conversion_rate DECIMAL(18,6) NULL,
        buy_box_percentage DECIMAL(18,6) NULL,
        currency NVARCHAR(10) NULL,
        raw_data NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_finance_event', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_finance_event (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        marketplace NVARCHAR(50) NOT NULL,
        posted_date DATETIME2 NOT NULL,
        order_id NVARCHAR(200) NULL,
        sku NVARCHAR(200) NULL,
        asin NVARCHAR(50) NULL,
        event_type NVARCHAR(120) NULL,
        amount_type NVARCHAR(120) NULL,
        amount_description NVARCHAR(300) NULL,
        amount DECIMAL(18,4) NOT NULL DEFAULT 0,
        currency NVARCHAR(10) NULL,
        raw_data NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_ads_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_ads_daily (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        marketplace NVARCHAR(50) NOT NULL,
        ads_date DATE NOT NULL,
        campaign_id NVARCHAR(100) NULL,
        campaign_name NVARCHAR(300) NULL,
        ad_group_id NVARCHAR(100) NULL,
        ad_group_name NVARCHAR(300) NULL,
        targeting_text NVARCHAR(500) NULL,
        sku NVARCHAR(200) NULL,
        asin NVARCHAR(50) NULL,
        impressions INT NOT NULL DEFAULT 0,
        clicks INT NOT NULL DEFAULT 0,
        spend DECIMAL(18,4) NOT NULL DEFAULT 0,
        attributed_sales DECIMAL(18,4) NOT NULL DEFAULT 0,
        attributed_orders INT NOT NULL DEFAULT 0,
        currency NVARCHAR(10) NULL,
        raw_data NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_inventory_daily', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_inventory_daily (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        marketplace NVARCHAR(50) NOT NULL,
        inventory_date DATE NOT NULL,
        sku NVARCHAR(200) NOT NULL,
        asin NVARCHAR(50) NULL,
        available_quantity INT NOT NULL DEFAULT 0,
        reserved_quantity INT NOT NULL DEFAULT 0,
        inbound_quantity INT NOT NULL DEFAULT 0,
        fulfillable_quantity INT NOT NULL DEFAULT 0,
        raw_data NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_periodic_report_snapshot', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_periodic_report_snapshot (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        marketplace NVARCHAR(50) NOT NULL,
        period_type NVARCHAR(50) NOT NULL,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        version INT NOT NULL DEFAULT 1,
        status NVARCHAR(50) NOT NULL DEFAULT 'draft',
        sales_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
        units_sold INT NOT NULL DEFAULT 0,
        orders_count INT NOT NULL DEFAULT 0,
        amazon_fees DECIMAL(18,4) NOT NULL DEFAULT 0,
        fba_fees DECIMAL(18,4) NOT NULL DEFAULT 0,
        refund_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
        ad_spend DECIMAL(18,4) NOT NULL DEFAULT 0,
        promotion_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
        product_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
        first_mile_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
        other_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
        estimated_profit DECIMAL(18,4) NOT NULL DEFAULT 0,
        currency NVARCHAR(10) NULL,
        generated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.amazon_report_generation_log', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.amazon_report_generation_log (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        report_name NVARCHAR(200) NOT NULL,
        period_type NVARCHAR(50) NOT NULL,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        version INT NOT NULL DEFAULT 1,
        file_path NVARCHAR(500) NULL,
        email_sent BIT NOT NULL DEFAULT 0,
        status NVARCHAR(50) NOT NULL DEFAULT 'created',
        error_detail NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO
