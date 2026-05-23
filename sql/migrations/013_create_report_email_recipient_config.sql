-- SellerDataPipeline migration 013: create report email recipient configuration table.
-- Created: 2026-05-23
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason: Store report delivery recipient routing in Azure SQL instead of local runtime JSON.

IF OBJECT_ID('dbo.report_email_recipient_config', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.report_email_recipient_config (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        report_type NVARCHAR(80) NOT NULL,
        audience NVARCHAR(80) NOT NULL,
        recipient_type NVARCHAR(10) NOT NULL,
        email NVARCHAR(320) NOT NULL,
        display_name NVARCHAR(200) NULL,
        enabled BIT NOT NULL
            CONSTRAINT DF_report_email_recipient_config_enabled DEFAULT (1),
        sort_order INT NOT NULL
            CONSTRAINT DF_report_email_recipient_config_sort_order DEFAULT (100),
        notes NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL
            CONSTRAINT DF_report_email_recipient_config_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL
            CONSTRAINT DF_report_email_recipient_config_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_report_email_recipient_config_recipient_type CHECK (
            recipient_type IN ('to', 'cc', 'bcc')
        ),
        CONSTRAINT CK_report_email_recipient_config_report_type_nonempty CHECK (
            LEN(LTRIM(RTRIM(report_type))) > 0
        ),
        CONSTRAINT CK_report_email_recipient_config_audience_nonempty CHECK (
            LEN(LTRIM(RTRIM(audience))) > 0
        ),
        CONSTRAINT CK_report_email_recipient_config_email_nonempty CHECK (
            LEN(LTRIM(RTRIM(email))) > 0
        ),
        CONSTRAINT CK_report_email_recipient_config_sort_order CHECK (
            sort_order >= 0
        )
    );
END
GO

/* =========================================================
   Unique route key and lookup indexes
   ========================================================= */
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.report_email_recipient_config')
      AND name = 'UX_report_email_recipient_config_active_route'
)
BEGIN
    CREATE UNIQUE INDEX UX_report_email_recipient_config_active_route
    ON dbo.report_email_recipient_config (
        report_type,
        audience,
        recipient_type,
        email
    )
    WHERE enabled = 1;
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.report_email_recipient_config')
      AND name = 'IX_report_email_recipient_config_lookup'
)
BEGIN
    CREATE INDEX IX_report_email_recipient_config_lookup
    ON dbo.report_email_recipient_config (
        enabled,
        report_type,
        audience,
        recipient_type,
        sort_order
    )
    INCLUDE (email, display_name);
END
GO
