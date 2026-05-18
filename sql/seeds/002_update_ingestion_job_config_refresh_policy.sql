-- SellerDataPipeline seed 002: refresh cadence policy update.
-- Safe to re-run. This keeps data refresh windows separate from weekly analysis/report generation.

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'day',
    recommended_cadence_value = 2,
    default_lookback_days = 14,
    data_window_lag_days = 3,
    notes = 'Rolling refresh every 2 days; refresh a 14-day window to capture attribution restatements. Analysis output remains weekly or longer.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.ads_sp_core.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'week',
    recommended_cadence_value = 1,
    default_lookback_days = 1,
    data_window_lag_days = 0,
    notes = 'Snapshot source. Run weekly or immediately after material listing changes; not used as a daily analysis output.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.listing_snapshot.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'day',
    recommended_cadence_value = 2,
    default_lookback_days = 1,
    data_window_lag_days = 0,
    notes = 'Snapshot source. Run every 2 days in the core refresh loop so weekly reports have recent stock balance.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.inventory_snapshot.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'day',
    recommended_cadence_value = 2,
    default_lookback_days = 10,
    data_window_lag_days = 2,
    notes = 'Rolling refresh every 2 days; refresh a 10-day window. Weekly analysis should use the source-specific stable cutoff, not today/yesterday.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.sales_traffic.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'week',
    recommended_cadence_value = 1,
    default_lookback_days = 60,
    data_window_lag_days = 0,
    notes = 'Settlement is Amazon-generated and remains the financial source of truth. Run weekly discovery/ingestion over a 60-day window.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.settlement.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'day',
    recommended_cadence_value = 2,
    default_lookback_days = 10,
    data_window_lag_days = 2,
    notes = 'Rolling refresh every 2 days; refresh a 10-day window. Used for weekly SKU/order context, not financial revenue.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.orders.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'week',
    recommended_cadence_value = 1,
    default_lookback_days = 60,
    data_window_lag_days = 7,
    notes = 'Run weekly with a 60-day rolling window because reimbursements can arrive late.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.fba_reimbursements.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'week',
    recommended_cadence_value = 1,
    default_lookback_days = 1,
    data_window_lag_days = 0,
    notes = 'Snapshot/reference source. Run weekly or after price/dimension/fee-impacting changes.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.fba_fee_preview.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'day',
    recommended_cadence_value = 2,
    default_lookback_days = 30,
    data_window_lag_days = 2,
    notes = 'Rolling refresh every 2 days during active promotion/coupon periods; weekly is enough when no campaign is active. Refresh a 30-day window.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.promotion_coupon.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'week',
    recommended_cadence_value = 1,
    default_lookback_days = 30,
    data_window_lag_days = 3,
    notes = 'Run weekly with a 30-day window for inventory movement explanation and anomaly review.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.ingest.inventory_ledger.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'week',
    recommended_cadence_value = 1,
    default_lookback_days = 7,
    data_window_lag_days = 2,
    enabled = 1,
    notes = 'Implemented as manual profit preview. Analysis cadence is weekly or longer; do not run daily profit conclusions.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.process.profit_weekly.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'week',
    recommended_cadence_value = 1,
    default_lookback_days = 7,
    data_window_lag_days = 2,
    notes = 'Planned weekly operations report. Minimum analysis interval is weekly; generated only after coverage audit and profit review.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.report.weekly_operations.us';

UPDATE dbo.pipeline_job_config
SET
    recommended_cadence_unit = 'week',
    recommended_cadence_value = 1,
    data_window_lag_days = NULL,
    notes = 'Planned weekly email/draft delivery after manual report approval. Never sends daily operational conclusions.',
    updated_at = SYSUTCDATETIME()
WHERE job_key = 'manual.email.weekly_operations.us';
GO
