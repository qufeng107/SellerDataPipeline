-- SellerDataPipeline migration 014: create pipeline artifact store.
-- Created: 2026-05-24
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason: Persist small cross-job runtime/report artifacts in Azure SQL for free-first automation.

IF OBJECT_ID('dbo.pipeline_artifact_store', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pipeline_artifact_store (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        artifact_type NVARCHAR(80) NOT NULL,
        artifact_scope NVARCHAR(200) NOT NULL,
        relative_path NVARCHAR(600) NOT NULL,
        content_type NVARCHAR(120) NULL,
        content_encoding NVARCHAR(40) NOT NULL
            CONSTRAINT DF_pipeline_artifact_store_content_encoding DEFAULT ('gzip'),
        content_sha256 CHAR(64) NOT NULL,
        content_size_bytes BIGINT NOT NULL,
        compressed_size_bytes BIGINT NOT NULL,
        content_bytes VARBINARY(MAX) NOT NULL,
        metadata_json NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_artifact_store_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL
            CONSTRAINT DF_pipeline_artifact_store_updated_at DEFAULT SYSUTCDATETIME(),
        expires_at DATETIME2 NULL,
        archived_at DATETIME2 NULL,
        is_deleted BIT NOT NULL
            CONSTRAINT DF_pipeline_artifact_store_is_deleted DEFAULT (0),
        CONSTRAINT CK_pipeline_artifact_store_artifact_type_nonempty CHECK (
            LEN(LTRIM(RTRIM(artifact_type))) > 0
        ),
        CONSTRAINT CK_pipeline_artifact_store_artifact_scope_nonempty CHECK (
            LEN(LTRIM(RTRIM(artifact_scope))) > 0
        ),
        CONSTRAINT CK_pipeline_artifact_store_relative_path_nonempty CHECK (
            LEN(LTRIM(RTRIM(relative_path))) > 0
        ),
        CONSTRAINT CK_pipeline_artifact_store_content_encoding CHECK (
            content_encoding IN ('gzip')
        ),
        CONSTRAINT CK_pipeline_artifact_store_sha256_len CHECK (
            LEN(content_sha256) = 64
        ),
        CONSTRAINT CK_pipeline_artifact_store_size_nonnegative CHECK (
            content_size_bytes >= 0 AND compressed_size_bytes >= 0
        ),
        CONSTRAINT CK_pipeline_artifact_store_metadata_json CHECK (
            metadata_json IS NULL OR ISJSON(metadata_json) = 1
        )
    );
END
GO

/* =========================================================
   Uniqueness and lookup indexes
   ========================================================= */
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_artifact_store')
      AND name = 'UX_pipeline_artifact_store_scope_path_hash_active'
)
BEGIN
    CREATE UNIQUE INDEX UX_pipeline_artifact_store_scope_path_hash_active
    ON dbo.pipeline_artifact_store (
        artifact_scope,
        relative_path,
        content_sha256
    )
    WHERE is_deleted = 0;
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_artifact_store')
      AND name = 'IX_pipeline_artifact_store_scope_type_created'
)
BEGIN
    CREATE INDEX IX_pipeline_artifact_store_scope_type_created
    ON dbo.pipeline_artifact_store (
        artifact_scope,
        artifact_type,
        created_at DESC
    )
    INCLUDE (relative_path, content_sha256, content_size_bytes, compressed_size_bytes, expires_at);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_artifact_store')
      AND name = 'IX_pipeline_artifact_store_scope_path_created'
)
BEGIN
    CREATE INDEX IX_pipeline_artifact_store_scope_path_created
    ON dbo.pipeline_artifact_store (
        artifact_scope,
        relative_path,
        created_at DESC
    )
    INCLUDE (artifact_type, content_sha256, expires_at, is_deleted);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pipeline_artifact_store')
      AND name = 'IX_pipeline_artifact_store_expiry_active'
)
BEGIN
    CREATE INDEX IX_pipeline_artifact_store_expiry_active
    ON dbo.pipeline_artifact_store (expires_at)
    INCLUDE (artifact_scope, relative_path, artifact_type)
    WHERE is_deleted = 0 AND expires_at IS NOT NULL;
END
GO
