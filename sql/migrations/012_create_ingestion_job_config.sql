-- SellerDataPipeline migration 012: create pipeline job configuration table.
-- This migration records recommended manual and future scheduled job cadence.

IF OBJECT_ID('dbo.pipeline_job_config', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pipeline_job_config (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        job_key NVARCHAR(160) NOT NULL,
        job_group NVARCHAR(40) NOT NULL,
        job_name NVARCHAR(240) NOT NULL,
        source_system NVARCHAR(50) NULL,
        marketplace_id NVARCHAR(50) NULL,
        profile_id NVARCHAR(100) NULL,
        data_domain NVARCHAR(80) NOT NULL,
        report_type NVARCHAR(180) NULL,
        target_table NVARCHAR(300) NULL,
        script_path NVARCHAR(500) NOT NULL,
        default_args_json NVARCHAR(MAX) NULL,
        manual_run_order INT NULL,
        recommended_cadence_unit NVARCHAR(20) NOT NULL,
        recommended_cadence_value INT NOT NULL
            CONSTRAINT DF_pipeline_job_config_cadence_value DEFAULT (1),
        default_lookback_days INT NULL,
        data_window_lag_days INT NULL,
        execution_phase NVARCHAR(40) NOT NULL
            CONSTRAINT DF_pipeline_job_config_execution_phase DEFAULT ('manual_first'),
        enabled BIT NOT NULL
            CONSTRAINT DF_pipeline_job_config_enabled DEFAULT (1),
        notes NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_config_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_config_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_pipeline_job_config_job_group CHECK (
            job_group IN ('download', 'ingest', 'process', 'report', 'email')
        ),
        CONSTRAINT CK_pipeline_job_config_cadence_unit CHECK (
            recommended_cadence_unit IN ('hour', 'day', 'week', 'month', 'on_demand')
        ),
        CONSTRAINT CK_pipeline_job_config_cadence_value CHECK (
            recommended_cadence_value >= 0
        ),
        CONSTRAINT CK_pipeline_job_config_execution_phase CHECK (
            execution_phase IN (
                'manual_first',
                'scheduled_candidate',
                'scheduled_active',
                'deprecated'
            )
        ),
        CONSTRAINT CK_pipeline_job_config_default_args_json CHECK (
            default_args_json IS NULL OR ISJSON(default_args_json) = 1
        )
    );
END
GO

/* =========================================================
   Unique key and lookup indexes
   ========================================================= */
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_config')
      AND name = 'UX_pipeline_job_config_job_key'
)
BEGIN
    CREATE UNIQUE INDEX UX_pipeline_job_config_job_key
    ON dbo.pipeline_job_config (job_key);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_config')
      AND name = 'IX_pipeline_job_config_enabled_phase'
)
BEGIN
    CREATE INDEX IX_pipeline_job_config_enabled_phase
    ON dbo.pipeline_job_config (enabled, execution_phase, job_group, manual_run_order);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_config')
      AND name = 'IX_pipeline_job_config_marketplace_domain'
)
BEGIN
    CREATE INDEX IX_pipeline_job_config_marketplace_domain
    ON dbo.pipeline_job_config (marketplace_id, data_domain, job_group);
END
GO
