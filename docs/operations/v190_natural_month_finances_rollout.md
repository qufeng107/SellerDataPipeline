# v1.90 Natural-Month Finances Azure Rollout

> Goal: deploy the Finances API natural-month ledger without sending historical emails.

## Gate 0 — CI

Push/merge v1.90 and require the normal CI quality gate to pass. Do not bypass Ruff/Safety lint.

## Gate 1 — migration 016

Before any production monthly collect/report job uses v1.90, run migration 016 from a v1.90 checkout/container (a one-off Container Apps execution is preferred so the three production monthly jobs can remain on v1.89 during validation):

```bash
python scripts/run_sql_migration.py \
  --sql-file sql/migrations/016_create_finances_natural_month_ledger.sql
```

Then verify `dbo.amazon_finance_transaction` and its two indexes exist.

## Gate 2 — historical dry-run

Run May, June and July without `--execute` first:

```bash
for MONTH in 2026-05 2026-06 2026-07
do
  python scripts/ingest_finances_natural_month.py \
    --marketplace-id ATVPDKIKX0DER \
    --month "$MONTH"
done
```

Required:

```text
review_required=0
```

Expected Seller Central reconciliation anchors:

```text
2026-05: Order 1915.68 / Refund -355.95 / Liquidation 2.30
2026-06: Order 2184.16 / Refund -380.50 / Liquidation 0.55
2026-07: Order 1097.24 / Refund -209.00 / Liquidation 2.08
```

Also verify extracted shipment/liquidation unit counts against the known Seller Central quantities before SQL write:

```text
2026-05: shipment 94 / liquidation 5
2026-06: shipment 120 / liquidation 2
2026-07: shipment 58 / liquidation 4
```

Any included Shipment / RemovalShipment with incomplete item-level SKU/quantity extraction is marked `review_required` and blocks execute.

## Gate 3 — execute backfill

Only after Gate 2:

```bash
for MONTH in 2026-05 2026-06 2026-07
do
  python scripts/ingest_finances_natural_month.py \
    --marketplace-id ATVPDKIKX0DER \
    --month "$MONTH" \
    --execute
done
```

Rerun the same three execute commands once. Expected second run:

```text
inserted=0
updated=N
```

## Gate 4 — SQL read-only postcheck

Verify by month:

- row count / distinct transaction_id equal;
- `review_required=0`;
- only USD for US marketplace;
- management included totals match the dry-run summary;
- no duplicate `business_key_hash`;
- timezone is `America/Los_Angeles`.

## Gate 5 — monthly report preview

Generate 2026-05, 2026-06, 2026-07 previews only. Do **not** use `--force-resend`.

Required report check:

```text
finances_natural_month_coverage = ok
```

Management P&L must use `natural_month_finance`; Settlement Close remains separate.

## Gate 6 — production job image

After historical backfill/report preview passes, update:

```text
sdp-monthly-submit
sdp-monthly-collect-ingest
sdp-monthly-report-delivery
```

to the same v1.90 SHA. Weekly jobs are out of scope for this change.

## Rollback

Migration 016 is additive. If v1.90 application behavior fails, roll monthly jobs back to the previous image. Do not drop the new table during incident response. Existing Settlement tables and historical send guards are untouched.
