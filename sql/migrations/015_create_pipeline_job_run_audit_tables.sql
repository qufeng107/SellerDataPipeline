-- SellerDataPipeline migration 015: create pipeline job run audit tables.
-- Created: 2026-05-29
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason: Persist structured automation job run audit lineage for weekly/monthly data pipelines.

IF OBJECT_ID('dbo.pipeline_job_run', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pipeline_job_run (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        run_uid UNIQUEIDENTIFIER NOT NULL
            CONSTRAINT DF_pipeline_job_run_uid DEFAULT NEWID(),
        workflow NVARCHAR(40) NOT NULL,
        phase NVARCHAR(40) NOT NULL,
        execution_mode NVARCHAR(20) NOT NULL,
        configured_trigger_type NVARCHAR(40) NULL,
        run_trigger_type NVARCHAR(40) NULL,
        run_trigger_source NVARCHAR(160) NULL,
        marketplace_id NVARCHAR(50) NULL,
        profile_id NVARCHAR(100) NULL,
        period_key NVARCHAR(80) NULL,
        stats_start DATE NULL,
        stats_end DATE NULL,
        request_start DATE NULL,
        request_end DATE NULL,
        artifact_scope NVARCHAR(220) NOT NULL,
        azure_resource_group NVARCHAR(200) NULL,
        azure_job_name NVARCHAR(200) NULL,
        azure_execution_name NVARCHAR(300) NULL,
        container_app_name NVARCHAR(200) NULL,
        container_revision NVARCHAR(200) NULL,
        container_replica NVARCHAR(200) NULL,
        container_image NVARCHAR(500) NULL,
        image_tag NVARCHAR(120) NULL,
        git_sha NVARCHAR(80) NULL,
        command_line_hash CHAR(64) NULL,
        status NVARCHAR(40) NOT NULL
            CONSTRAINT DF_pipeline_job_run_status DEFAULT ('running'),
        started_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_run_started_at DEFAULT SYSUTCDATETIME(),
        finished_at DATETIME2 NULL,
        duration_ms BIGINT NULL,
        commands_total INT NOT NULL
            CONSTRAINT DF_pipeline_job_run_commands_total DEFAULT (0),
        commands_failed INT NOT NULL
            CONSTRAINT DF_pipeline_job_run_commands_failed DEFAULT (0),
        artifact_restored_count INT NOT NULL
            CONSTRAINT DF_pipeline_job_run_artifact_restored_count DEFAULT (0),
        artifact_saved_count INT NOT NULL
            CONSTRAINT DF_pipeline_job_run_artifact_saved_count DEFAULT (0),
        artifact_skipped_count INT NOT NULL
            CONSTRAINT DF_pipeline_job_run_artifact_skipped_count DEFAULT (0),
        error_type NVARCHAR(200) NULL,
        error_summary NVARCHAR(MAX) NULL,
        config_snapshot_json NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_run_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_run_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_pipeline_job_run_workflow CHECK (workflow IN ('weekly', 'monthly')),
        CONSTRAINT CK_pipeline_job_run_phase CHECK (phase IN ('submit', 'collect_ingest', 'report_delivery')),
        CONSTRAINT CK_pipeline_job_run_execution_mode CHECK (execution_mode IN ('dry_run', 'execute')),
        CONSTRAINT CK_pipeline_job_run_status CHECK (status IN ('running', 'succeeded', 'failed', 'partial', 'skipped', 'blocked')),
        CONSTRAINT CK_pipeline_job_run_artifact_scope_nonempty CHECK (LEN(LTRIM(RTRIM(artifact_scope))) > 0),
        CONSTRAINT CK_pipeline_job_run_command_line_hash_len CHECK (command_line_hash IS NULL OR LEN(command_line_hash) = 64),
        CONSTRAINT CK_pipeline_job_run_counts_nonnegative CHECK (
            commands_total >= 0
            AND commands_failed >= 0
            AND artifact_restored_count >= 0
            AND artifact_saved_count >= 0
            AND artifact_skipped_count >= 0
            AND (duration_ms IS NULL OR duration_ms >= 0)
        ),
        CONSTRAINT CK_pipeline_job_run_config_json CHECK (
            config_snapshot_json IS NULL OR ISJSON(config_snapshot_json) = 1
        )
    );
END
GO

IF OBJECT_ID('dbo.pipeline_job_command_run', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pipeline_job_command_run (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        job_run_id BIGINT NOT NULL,
        command_index INT NOT NULL,
        command_label NVARCHAR(240) NOT NULL,
        script_path NVARCHAR(500) NOT NULL,
        redacted_args_json NVARCHAR(MAX) NULL,
        args_sha256 CHAR(64) NULL,
        writes_external_or_database BIT NOT NULL
            CONSTRAINT DF_pipeline_job_command_run_writes DEFAULT (0),
        status NVARCHAR(40) NOT NULL
            CONSTRAINT DF_pipeline_job_command_run_status DEFAULT ('running'),
        exit_code INT NULL,
        started_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_command_run_started_at DEFAULT SYSUTCDATETIME(),
        finished_at DATETIME2 NULL,
        duration_ms BIGINT NULL,
        rows_read INT NULL,
        rows_inserted INT NULL,
        rows_updated INT NULL,
        rows_skipped INT NULL,
        rows_failed INT NULL,
        files_created INT NULL,
        error_type NVARCHAR(200) NULL,
        error_summary NVARCHAR(MAX) NULL,
        output_summary_json NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_command_run_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_command_run_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_pipeline_job_command_run_job_run FOREIGN KEY (job_run_id)
            REFERENCES dbo.pipeline_job_run(id),
        CONSTRAINT UX_pipeline_job_command_run_index UNIQUE (job_run_id, command_index),
        CONSTRAINT CK_pipeline_job_command_run_index_positive CHECK (command_index > 0),
        CONSTRAINT CK_pipeline_job_command_run_status CHECK (status IN ('running', 'succeeded', 'failed', 'partial', 'skipped', 'blocked')),
        CONSTRAINT CK_pipeline_job_command_run_args_hash_len CHECK (args_sha256 IS NULL OR LEN(args_sha256) = 64),
        CONSTRAINT CK_pipeline_job_command_run_counts_nonnegative CHECK (
            (duration_ms IS NULL OR duration_ms >= 0)
            AND (rows_read IS NULL OR rows_read >= 0)
            AND (rows_inserted IS NULL OR rows_inserted >= 0)
            AND (rows_updated IS NULL OR rows_updated >= 0)
            AND (rows_skipped IS NULL OR rows_skipped >= 0)
            AND (rows_failed IS NULL OR rows_failed >= 0)
            AND (files_created IS NULL OR files_created >= 0)
        ),
        CONSTRAINT CK_pipeline_job_command_run_args_json CHECK (
            redacted_args_json IS NULL OR ISJSON(redacted_args_json) = 1
        ),
        CONSTRAINT CK_pipeline_job_command_run_output_json CHECK (
            output_summary_json IS NULL OR ISJSON(output_summary_json) = 1
        )
    );
END
GO

IF OBJECT_ID('dbo.pipeline_job_artifact_link', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pipeline_job_artifact_link (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        job_run_id BIGINT NOT NULL,
        command_run_id BIGINT NULL,
        artifact_id BIGINT NOT NULL,
        artifact_role NVARCHAR(40) NOT NULL,
        artifact_type NVARCHAR(80) NOT NULL,
        artifact_scope NVARCHAR(220) NOT NULL,
        relative_path NVARCHAR(600) NOT NULL,
        content_sha256 CHAR(64) NOT NULL,
        content_size_bytes BIGINT NULL,
        created_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_artifact_link_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_pipeline_job_artifact_link_job_run FOREIGN KEY (job_run_id)
            REFERENCES dbo.pipeline_job_run(id),
        CONSTRAINT FK_pipeline_job_artifact_link_command_run FOREIGN KEY (command_run_id)
            REFERENCES dbo.pipeline_job_command_run(id),
        CONSTRAINT FK_pipeline_job_artifact_link_artifact FOREIGN KEY (artifact_id)
            REFERENCES dbo.pipeline_artifact_store(id),
        CONSTRAINT CK_pipeline_job_artifact_link_role CHECK (
            artifact_role IN (
                'restored_input',
                'saved_output',
                'raw_report',
                'request_manifest',
                'ingestion_output',
                'coverage_audit',
                'analysis_report',
                'report_delivery_pack',
                'email_send_result',
                'automation_audit'
            )
        ),
        CONSTRAINT CK_pipeline_job_artifact_link_sha_len CHECK (LEN(content_sha256) = 64),
        CONSTRAINT CK_pipeline_job_artifact_link_size_nonnegative CHECK (
            content_size_bytes IS NULL OR content_size_bytes >= 0
        )
    );
END
GO

IF OBJECT_ID('dbo.pipeline_job_table_write_summary', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pipeline_job_table_write_summary (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        job_run_id BIGINT NOT NULL,
        command_run_id BIGINT NULL,
        target_table NVARCHAR(300) NOT NULL,
        source_system NVARCHAR(50) NULL,
        source_report_type NVARCHAR(180) NULL,
        source_report_id NVARCHAR(180) NULL,
        source_raw_file_path NVARCHAR(1000) NULL,
        source_raw_file_sha256 CHAR(64) NULL,
        data_start_date DATE NULL,
        data_end_date DATE NULL,
        rows_read INT NULL,
        rows_inserted INT NULL,
        rows_updated INT NULL,
        rows_skipped INT NULL,
        rows_failed INT NULL,
        status NVARCHAR(40) NOT NULL
            CONSTRAINT DF_pipeline_job_table_write_summary_status DEFAULT ('succeeded'),
        summary_json NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_job_table_write_summary_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_pipeline_job_table_write_summary_job_run FOREIGN KEY (job_run_id)
            REFERENCES dbo.pipeline_job_run(id),
        CONSTRAINT FK_pipeline_job_table_write_summary_command_run FOREIGN KEY (command_run_id)
            REFERENCES dbo.pipeline_job_command_run(id),
        CONSTRAINT CK_pipeline_job_table_write_summary_status CHECK (status IN ('succeeded', 'failed', 'partial', 'skipped', 'blocked')),
        CONSTRAINT CK_pipeline_job_table_write_summary_sha_len CHECK (
            source_raw_file_sha256 IS NULL OR LEN(source_raw_file_sha256) = 64
        ),
        CONSTRAINT CK_pipeline_job_table_write_summary_counts_nonnegative CHECK (
            (rows_read IS NULL OR rows_read >= 0)
            AND (rows_inserted IS NULL OR rows_inserted >= 0)
            AND (rows_updated IS NULL OR rows_updated >= 0)
            AND (rows_skipped IS NULL OR rows_skipped >= 0)
            AND (rows_failed IS NULL OR rows_failed >= 0)
        ),
        CONSTRAINT CK_pipeline_job_table_write_summary_json CHECK (
            summary_json IS NULL OR ISJSON(summary_json) = 1
        )
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_run')
      AND name = 'UX_pipeline_job_run_uid'
)
BEGIN
    CREATE UNIQUE INDEX UX_pipeline_job_run_uid ON dbo.pipeline_job_run (run_uid);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_run')
      AND name = 'IX_pipeline_job_run_scope_phase_started'
)
BEGIN
    CREATE INDEX IX_pipeline_job_run_scope_phase_started
    ON dbo.pipeline_job_run (artifact_scope, phase, started_at DESC)
    INCLUDE (workflow, status, azure_job_name, azure_execution_name, commands_failed);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_run')
      AND name = 'IX_pipeline_job_run_status_started'
)
BEGIN
    CREATE INDEX IX_pipeline_job_run_status_started
    ON dbo.pipeline_job_run (status, started_at DESC)
    INCLUDE (workflow, phase, artifact_scope, azure_job_name);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_run')
      AND name = 'IX_pipeline_job_run_workflow_period'
)
BEGIN
    CREATE INDEX IX_pipeline_job_run_workflow_period
    ON dbo.pipeline_job_run (workflow, period_key, phase)
    INCLUDE (status, started_at, finished_at, artifact_scope);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_run')
      AND name = 'IX_pipeline_job_run_azure_job_started'
)
BEGIN
    CREATE INDEX IX_pipeline_job_run_azure_job_started
    ON dbo.pipeline_job_run (azure_job_name, started_at DESC)
    INCLUDE (workflow, phase, status, configured_trigger_type, run_trigger_type);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_command_run')
      AND name = 'IX_pipeline_job_command_run_script_started'
)
BEGIN
    CREATE INDEX IX_pipeline_job_command_run_script_started
    ON dbo.pipeline_job_command_run (script_path, started_at DESC)
    INCLUDE (job_run_id, command_label, status, exit_code);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_command_run')
      AND name = 'IX_pipeline_job_command_run_status_started'
)
BEGIN
    CREATE INDEX IX_pipeline_job_command_run_status_started
    ON dbo.pipeline_job_command_run (status, started_at DESC)
    INCLUDE (job_run_id, command_label, script_path, exit_code);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_artifact_link')
      AND name = 'UX_pipeline_job_artifact_link_run_command_artifact_role'
)
BEGIN
    CREATE UNIQUE INDEX UX_pipeline_job_artifact_link_run_command_artifact_role
    ON dbo.pipeline_job_artifact_link (
        job_run_id,
        command_run_id,
        artifact_id,
        artifact_role
    )
    WHERE command_run_id IS NOT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_artifact_link')
      AND name = 'UX_pipeline_job_artifact_link_run_artifact_role_no_command'
)
BEGIN
    CREATE UNIQUE INDEX UX_pipeline_job_artifact_link_run_artifact_role_no_command
    ON dbo.pipeline_job_artifact_link (job_run_id, artifact_id, artifact_role)
    WHERE command_run_id IS NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_artifact_link')
      AND name = 'IX_pipeline_job_artifact_link_scope_type'
)
BEGIN
    CREATE INDEX IX_pipeline_job_artifact_link_scope_type
    ON dbo.pipeline_job_artifact_link (artifact_scope, artifact_type)
    INCLUDE (job_run_id, artifact_role, relative_path, content_sha256);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_table_write_summary')
      AND name = 'IX_pipeline_job_table_write_target_date'
)
BEGIN
    CREATE INDEX IX_pipeline_job_table_write_target_date
    ON dbo.pipeline_job_table_write_summary (target_table, data_start_date, data_end_date)
    INCLUDE (job_run_id, command_run_id, rows_read, rows_inserted, rows_updated, rows_skipped, status);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_table_write_summary')
      AND name = 'IX_pipeline_job_table_write_run'
)
BEGIN
    CREATE INDEX IX_pipeline_job_table_write_run
    ON dbo.pipeline_job_table_write_summary (job_run_id, command_run_id)
    INCLUDE (target_table, rows_read, rows_inserted, rows_updated, rows_skipped, rows_failed, status);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_job_table_write_summary')
      AND name = 'IX_pipeline_job_table_write_source_report'
)
BEGIN
    CREATE INDEX IX_pipeline_job_table_write_source_report
    ON dbo.pipeline_job_table_write_summary (source_system, source_report_type, source_report_id)
    INCLUDE (job_run_id, target_table, status, created_at);
END
GO
