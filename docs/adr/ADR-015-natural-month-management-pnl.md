# ADR-015: Natural-Month Management P&L and Separate Settlement Close

- Status: Accepted / Production verified
- Date: 2026-08-10
- Decision scope: Amazon US monthly management P&L, Finances API ledger, Settlement close, COGS identity resolution
- Implementation: v1.90-v1.90.3

## Context

SellerDataPipeline historically used Settlement-led Financial Profit as the monthly financial baseline. Production reconciliation of 2026-05 / 06 / 07 showed that this remains useful for Amazon settlement/accounting close, but it is not a reliable natural-month operating view:

- Settlement V2 `posted-date` follows Amazon release/settlement timing, not the original operating month.
- late-generated Settlement reports can appear days after month-end;
- Seller Central Monthly Transaction assigns activity to the marketplace-local month, while an initial Finances API UTC-month query created boundary differences;
- Ads API spend is naturally interpreted by report date, so mixing report-date Ads with posted-date Settlement revenue creates a mixed-period Management P&L.

2026-07 provided a concrete proof: UTC-month Finances included two Shipment transactions totaling `35.90` and one Refund totaling `-22.00` that belonged to local June. Filtering by `America/Los_Angeles` local month removed those differences and exactly matched Seller Central Monthly Transaction.

## Decision

### 1. Two monthly views are maintained

```text
Management Operating P&L
  -> Finances API natural-month ledger
  -> marketplace local timezone
  -> Ads API report-date spend
  -> natural-month landed COGS

Settlement Close
  -> Settlement V2 posted/release timing
  -> accounting / cash / Amazon settlement reconciliation
```

Neither view overwrites the other.

### 2. Amazon US month boundary

Amazon US (`ATVPDKIKX0DER`) uses:

```text
America/Los_Angeles
```

UTC calendar months must not be used directly for Management P&L month assignment.

### 3. Verified Finances lifecycle policy

```text
Orders       = DEFERRED_RELEASED Shipment
Zero-$ units = RELEASED Shipment(amount=0), COGS unit only
Refunds      = RELEASED Refund
Liquidation  = DEFERRED + DEFERRED_RELEASED RemovalShipment
Ads charge   = RELEASED ProductAdsPayment, reconciliation reference only
Service Fee  = RELEASED ServiceFee
Reimburse    = RELEASED FBAInventoryReimbursement
Adjustment   = RELEASED MiscellaneousLedgerAdjustment
Transfer     = RELEASED Transfer, cash reference only
```

Known prior-period release combinations such as non-zero `RELEASED Shipment`, `DEFERRED_RELEASED Refund` and `RELEASED RemovalShipment` are excluded from current natural-month operating amounts. Unknown non-zero combinations fail closed.

### 4. Amount inclusion and COGS-unit inclusion are separate

Two June 2026 FBA orders were `RELEASED Shipment amount=0` but each contained one valid ProductContext unit. They do not increase revenue, but they must consume inventory cost. Therefore a zero-value Shipment can be excluded from revenue while still included in COGS units.

### 5. Cost identity resolution is conservative

Finances liquidation/removal events can return an FNSKU as `ProductContext.sku` and omit ASIN. Cost lookup order is:

```text
source SKU direct amazon_sku_cost match
-> else unique historical FNSKU -> Seller SKU mapping from amazon_inventory_daily
-> canonical Seller SKU effective-date cost
-> ambiguous / missing mapping or cost => needs_review
```

Only inventory snapshots with `snapshot_date <= target month end` can resolve historical identity. Direct Seller SKU cost always wins.

Verified examples:

```text
X004Q3AKFX -> HU-4XAJ-PYLD -> USD 6.94 all-in
X004WU7DSH -> SC-9HC3-5TFL -> USD 4.17 + 0.5271 first-mile
```

### 6. Fail-closed guards remain financial controls

A normal monthly report must not pass when any of the following is true:

- no Finances natural-month ledger for the month;
- non-zero unknown lifecycle/type combination;
- required Shipment/RemovalShipment unit has incomplete SKU/quantity;
- COGS identity cannot be resolved uniquely;
- extracted units and costed units differ;
- US ledger contains unexpected currency/timezone.

Historical send guards must not be overridden merely to make a report send.

## Production evidence

May/June/July Seller Central reconciliation anchors:

| Month | Orders | Refunds | Liquidation | Management units |
|---|---:|---:|---:|---:|
| 2026-05 | 1915.68 | -355.95 | 2.30 | 99 |
| 2026-06 | 2184.16 | -380.50 | 0.55 | 122 |
| 2026-07 | 1097.24 | -209.00 | 2.08 | 62 |

Final v1.90.2 report preview:

| Month | Product Sales | Landed COGS | Management Operating Profit | Margin |
|---|---:|---:|---:|---:|
| 2026-05 | 2316.38 | 467.25 | 548.35 | 23.67% |
| 2026-06 | 2870.06 | 573.05 | 612.70 | 21.35% |
| 2026-07 | 1464.14 | 291.23 | -114.89 | -7.85% |

v1.90.3 production image:

```text
ghcr.io/qufeng107/seller-data-pipeline:2fa19ad316720742d1871765fa0c1149c6b9fb9a
```

July production smoke execution:

```text
sdp-monthly-collect-ingest-cbacfwp
Status: Succeeded
2026-08-10T09:57:38Z -> 2026-08-10T10:09:32Z
Finances: attempted=161 inserted=0 updated=161 review_required=0
Settlement: attempted=1628 inserted=0 updated=1628
Automation: commands=11 failed=0
artifact_save: scanned=169 saved=169 skipped=0
```

## Consequences

Positive:

- Management P&L now measures a true marketplace-local natural month instead of a mixed timing basis.
- Settlement remains available for accounting close and bank/Amazon reconciliation.
- COGS is unit-complete even for zero-dollar FBA shipments.
- FNSKU liquidation identity can reuse existing canonical SKU costs without duplicating fake cost rows.
- lifecycle, cost and send-guard uncertainty fail closed.

Trade-offs:

- the system intentionally maintains two valid profit views;
- Finances lifecycle rules require regression tests when Amazon introduces new transaction/status combinations;
- marketplace timezone becomes mandatory metadata for future international expansion;
- a newly observed FNSKU may require inventory identity history before a report can pass.

## Related documents

- `docs/features/feature_finances_api_natural_month_ledger.md`
- `docs/features/feature_monthly_financial_close_report.md`
- `docs/operations/v190_natural_month_finances_rollout.md`
- `docs/operations/monthly_financial_troubleshooting.md`
- `docs/adr/ADR-009-settlement-led-profit-policy.md` — retained for the Settlement Close/accounting view; superseded as the sole Management P&L policy.
