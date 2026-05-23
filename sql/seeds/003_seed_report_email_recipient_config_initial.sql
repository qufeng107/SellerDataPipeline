-- SellerDataPipeline seed 003: initial report email recipients.
-- Status: pending until executed against Azure SQL amazon_ops after migration 013.
-- Safe to re-run. It enables the initial global recipient route for all report types/audiences.

IF OBJECT_ID('dbo.report_email_recipient_config', 'U') IS NULL
BEGIN
    THROW 51013, 'dbo.report_email_recipient_config does not exist. Run migration 013 first.', 1;
END
GO

DECLARE @now DATETIME2 = SYSUTCDATETIME();

MERGE dbo.report_email_recipient_config AS target
USING (
    SELECT '*' AS report_type, '*' AS audience, 'to' AS recipient_type,
           'feng@cuidena.cn' AS email, 'Feng' AS display_name, 10 AS sort_order,
           'Initial global recipient for all report delivery emails.' AS notes
    UNION ALL
    SELECT '*', '*', 'to', 'yufei@cuidena.cn', 'Yufei', 20,
           'Initial global recipient for all report delivery emails.'
    UNION ALL
    SELECT '*', '*', 'to', 'qian@cuidena.cn', 'Qian', 30,
           'Initial global recipient for all report delivery emails.'
) AS source
ON target.report_type = source.report_type
   AND target.audience = source.audience
   AND target.recipient_type = source.recipient_type
   AND target.email = source.email
WHEN MATCHED THEN
    UPDATE SET
        target.display_name = source.display_name,
        target.enabled = 1,
        target.sort_order = source.sort_order,
        target.notes = source.notes,
        target.updated_at = @now
WHEN NOT MATCHED THEN
    INSERT (
        report_type,
        audience,
        recipient_type,
        email,
        display_name,
        enabled,
        sort_order,
        notes,
        created_at,
        updated_at
    )
    VALUES (
        source.report_type,
        source.audience,
        source.recipient_type,
        source.email,
        source.display_name,
        1,
        source.sort_order,
        source.notes,
        @now,
        @now
    );
GO
