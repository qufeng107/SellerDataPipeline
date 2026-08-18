# ADR-017: Weekly Operating Review and Mature Ads Action Reporting

- Status: Accepted / implementation pending
- Date: 2026-08-16
- Decision scope: Weekly Business Review, Weekly Ads Optimization Report, weekly reconciliation and default workbook presentation
- Depends on: ADR-010 overlapping refresh weekly analysis; ADR-015 natural-month management P&L for terminology separation

## Context

The current weekly pipeline has a useful normalized-data foundation, but the default workbooks accumulated implementation-oriented sheets and do not yet provide the same decision-first experience as the redesigned monthly reports.

A code and artifact audit found four material issues:

1. WBR Orders are filtered by a direct SQL date conversion of `purchase_date_raw`, while Sales & Traffic uses marketplace-local report dates. For US data this can move late-evening Pacific orders into the following UTC day.
2. WBR Orders do not filter `sales_channel`, allowing non-target channel rows to enter SKU and COGS analysis.
3. WBR verifies that Orders rows exist but does not reconcile Orders sales/units against Sales & Traffic before trusting SKU/COGS/contribution calculations.
4. WAOR currently uses recent-week `sales_7d/purchases_7d` as if a short T-3 lag makes 7-day attribution mature enough for action decisions.

At the presentation layer, WBR currently exposes separate summary, daily, sales/traffic, SKU, ads, inventory, alerts, reconciliation and metadata sheets; WAOR exposes even more technical/detail sheets. The underlying detail is valuable for JSON/audit, but the default XLSX is larger than necessary for a small operating team.

## Decision

### 1. Weekly total sales/traffic remains Sales & Traffic-led

For WBR:

```text
Product Sales / Units / Sessions / Conversion
= amazon_sales_traffic_daily report-date business metrics
```

Orders is a supporting source for SKU-level sales estimates and effective-date landed COGS. It does not replace Sales & Traffic total sales.

### 2. Orders must use marketplace-local purchase date

For each marketplace, `purchase_date_raw` must be interpreted as a timestamp and converted to the marketplace timezone before deriving the business date.

US contract:

```text
ATVPDKIKX0DER -> America/Los_Angeles
```

The same local business date is used for:

- WBR period inclusion;
- effective-date SKU cost matching;
- Sales & Traffic ↔ Orders reconciliation.

### 3. Orders must be restricted to expected marketplace sales channel

The project shall use verified marketplace metadata to identify expected sales-channel names.

US contract:

```text
ATVPDKIKX0DER -> Amazon.com
```

Rows outside the expected sales channel are excluded from US WBR SKU/COGS analysis and are counted in audit metadata when present.

### 4. SKU/COGS contribution is fail-closed behind Sales & Traffic ↔ Orders reconciliation

Before WBR treats Orders-derived COGS/contribution as trusted, it must reconcile at least:

```text
Orders sales estimate vs Sales & Traffic ordered product sales
Orders units vs Sales & Traffic units ordered
```

Initial default tolerance:

```text
sales: abs(diff) <= max($5, 1% of S&T sales)
units: abs(diff) <= 1
```

If material mismatch remains:

- WBR total sales/traffic metrics remain usable;
- SKU diagnostic rows may remain visible;
- Orders-derived COGS and contribution become provisional / needs_review;
- `--fail-on-review` returns non-zero;
- executive conclusions must not present the contribution proxy as trusted.

### 5. Weekly contribution is explicitly a proxy, not profit

WBR may continue to calculate:

```text
Operating Contribution Proxy
= Sales & Traffic Product Sales
- reconciled landed COGS
- Ads API report-date spend
```

But the report must explicitly state that this does not include the complete set of Amazon fees, refunds, account/service fees and other natural-month P&L components.

The words `Operating Profit`, `Net Profit`, `经营利润` and `净利润` are reserved for the verified monthly Management P&L unless a future weekly financial ledger is independently designed and validated.

### 6. WBR default workbook is reduced to four decision-oriented sheets

```text
01_周度经营总览
02_SKU经营与库存
03_日趋势与广告
04_核验与口径
```

The former standalone Sales & Traffic, Ads Overview, Inventory Risk, Alerts/Actions, Reconciliation, Raw Metadata and Readme sheets are not required as separate default sheets.

Their data remains available through JSON, audit context and consolidated v2 sheets.

### 7. WBR adds four-week trend and deterministic driver diagnosis

The executive sheet shall show current week, previous week and recent four-week trend for the most important metrics.

It shall also distinguish likely drivers:

```text
traffic
conversion
price/mix
ads pressure
inventory constraint
```

Conclusions must be deterministic and source-driven in v2; LLM narrative generation is not required.

### 8. Recent Ads spend and mature Ads conversions are separate windows

For the scheduled weekly reports:

```text
Recent Spend Window
= requested WBR week

Mature Conversion Action Window
= requested WBR week shifted back 7 days
```

Recent window drives:

- spend;
- impressions;
- clicks;
- CTR;
- CPC;
- Ads Spend Ratio / TACOS against current Sales & Traffic.

Mature window drives:

- attributed sales_7d;
- purchases_7d;
- CVR;
- ACOS;
- ROAS;
- campaign/target/search-term conversion actions.

This deliberately sacrifices some action recency in exchange for materially better attribution maturity and repeatability.

### 9. WAOR default workbook is reduced to five action-oriented sheets

```text
01_广告周度总览
02_优先动作
03_Campaign与Targeting
04_SearchTerms
05_核验与口径
```

Default standalone sheets for historical paused lessons, negative snapshot, raw metadata and warning/reconciliation internals are removed from presentation.

Historical and negative-keyword evidence remains in JSON and continues to support action de-duplication.

### 10. WAOR default action list contains current actionable entities only

Paused/historical entities may be preserved as machine-readable lessons, but must not compete with current actionable items on the default action sheet.

Action rows must expose:

```text
priority
entity
action
reason
metric context
suggested manual action
already-done / negative-match state
confidence
```

### 11. Delivery routing is not changed in the first weekly v2 implementation

The existing report types and routes remain:

```text
weekly_business_review -> operations
weekly_ads_optimization -> ads_operator
```

The redesign shall first prove financial/operational correctness and workbook usability. A later ADR may choose to combine both files into one weekly email if that is operationally preferable.

### 12. No database migration is required by default

The v2 design shall first use existing normalized tables and marketplace metadata.

A migration may only be introduced if implementation demonstrates a concrete inability to provide the required local-date/reconciliation behavior from existing fields.

## Consequences

Positive:

- WBR becomes significantly smaller and easier to use in a weekly management meeting;
- SKU contribution cannot silently look healthy when Orders coverage is materially incomplete;
- US late-evening orders are assigned to the correct Pacific business date;
- non-Amazon.com order rows cannot contaminate US marketplace operating analysis;
- recent ad spend remains timely while conversion actions use a more mature attribution window;
- WAOR becomes an execution list instead of a collection of technical tables;
- JSON/audit detail is preserved without dominating the XLSX.

Trade-offs:

- WAOR conversion actions intentionally lag the recent spend week by one week;
- additional repository/service logic and tests are required for local date and channel filtering;
- contribution can become unavailable/needs_review on a week where Orders does not reconcile, which is preferable to reporting a misleading number;
- users wanting historical paused detail may need JSON/audit rather than the default XLSX.

## Golden validation

Required before production rollout:

1. `2026-04-06..2026-04-12`: US Orders local-date calculation must reconcile to S&T `$1,177 / 49 units`.
2. `2026-05-16..2026-05-22`: material Orders/S&T mismatch must be detected or explained; contribution must fail closed when unresolved.
3. A complete Ads period must prove recent-spend vs mature-conversion separation and confirm no action is driven by immature recent `sales_7d/purchases_7d`.
4. Existing negative-keyword dedupe, artifact store, report delivery and duplicate-send protection must not regress.

## Implementation order

```text
local date -> sales channel -> reconciliation gate
-> WBR 4-sheet presentation
-> WAOR dual-window calculation
-> WAOR 5-sheet presentation
-> unit tests -> historical golden -> Azure preview -> production image
```

## Related documents

- `docs/features/feature_weekly_reporting_pack_redesign.md`
- `docs/features/feature_weekly_business_review.md`
- `docs/features/feature_weekly_ads_optimization_report.md`
- `docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md`
- `docs/adr/ADR-015-natural-month-management-pnl.md`
