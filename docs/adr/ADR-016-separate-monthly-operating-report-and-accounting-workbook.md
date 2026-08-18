# ADR-016: Separate Monthly Operating Report and Accountant Workbook

- Status: Accepted / implemented; amended by ADR-018
- Date: 2026-08-12
- Decision scope: monthly report presentation, accounting support workbook, Seller Central reconciliation, report delivery artifacts
- Depends on: ADR-015 Natural-Month Management P&L

## Context

The v1.90.3 monthly financial pipeline has a production-verified financial core, but its XLSX presentation accumulated multiple generations of management, reconciliation, Settlement, accounting, journal-entry, FX, payout and raw-metadata sheets in one workbook.

That structure is technically rich but no longer matches how the outputs are used:

- management needs a compact monthly operating review that makes sales, margin, advertising burden, conversion and major cost drivers obvious;
- accounting needs a traceable bookkeeping support workbook based on Amazon transaction categories and source transactions;
- raw/audit evidence must remain available without dominating the default workbook;
- Settlement/Transfer and Ads billing timing are valid accounting/reconciliation views, but must not be confused with the marketplace-local Management Operating P&L.

A separate three-month board report was manually validated using May/June/July 2026 production data. Its compact structure proved materially easier to read than the current all-in-one monthly workbook. The same period was also reconciled against Seller Central Monthly Transaction exports, confirming that the normalized Finances ledger can reproduce the important posted-date categories used for bookkeeping.

## Decision

### 1. Monthly delivery is split into two audience-specific XLSX artifacts

The monthly report-delivery stage shall produce two distinct workbooks from the same verified monthly financial core:

```text
A. Monthly Operating Report
   audience: owner / management / board
   purpose: operating performance and decisions

B. Accountant Workbook
   audience: accountant / bookkeeping support
   purpose: transaction classification, accounting support and traceability
```

The existing JSON financial-close artifact remains the machine-readable source of truth. This ADR changes the default presentation contract, not the verified Management P&L formula.

### 2. Monthly Operating Report uses three sheets only

Default workbook contract:

```text
01_月度经营总览
02_经营损益
03_核验与口径
```

The first sheet is decision-first and must prioritize:

- Product Sales / 商品销售额
- Product Gross Margin / 商品毛利率（仅扣到岸商品成本）
- Management Operating Profit / 经营利润
- Operating Margin / 经营利润率
- Ads Spend Ratio / 广告费率
- Management Units / 管理口径销量
- Sessions
- Sales & Traffic conversion rate
- current-month major expense structure
- recent three-month trend
- concise explanations of the key percentage metrics
- concise current-month conclusions / anomalies

The report must not require the reader to understand Settlement timing, payout mechanics or raw API structures in order to understand operating performance.

### 3. Product Gross Margin has an explicit limited definition

For this project:

```text
Product Gross Margin
= (Product Sales - Landed COGS) / Product Sales
```

`Landed COGS` includes the SKU-effective product cost and first-mile cost, plus packaging/other unit cost when configured.

This metric intentionally does **not** deduct:

- FBA fulfillment fees;
- Amazon account/service fees;
- refunds;
- promotions / Coupons / Deals;
- advertising spend;
- storage fees;
- other operating charges.

Therefore it is a product economics indicator, not the final company profit margin. The workbook must explain this distinction next to Operating Margin.

### 4. Accountant Workbook is a separate compact support pack

Default workbook contract:

```text
01_会计汇总
02_分类明细
03_源交易明细
04_核验与说明
```

`01_会计汇总` should show accounting-friendly categories such as:

- product sales revenue;
- shipping revenue;
- order promotional rebates;
- FBA / Amazon order fees;
- refunds;
- posted-date advertising billing / advertiser refunds;
- subscription and account service fees;
- Coupon / Deal fees;
- FBA storage / return-processing / other service fees;
- reimbursements / adjustments;
- liquidation net amount;
- Amazon transaction net amount excluding Transfer;
- product cost and first-mile cost;
- optional bookkeeping/reference profit;
- Management Operating Profit and Ads API spend only as clearly labeled reference rows.

This workbook is an accounting support workbook, not a statutory financial statement or tax filing.

### 5. Automatic generation must not depend on a monthly manual CSV upload

The production pipeline shall generate the Accountant Workbook from the normalized `amazon_finance_transaction` ledger and existing SKU-cost data.

Seller Central Monthly Transaction remains an important independent official reconciliation source, but is not a hard dependency for normal automated report generation.

When a manual Monthly Transaction export is supplied, it may be reconciled against the generated accounting categories. Absence of the manual file shall not prevent the normal automated Accountant Workbook from being created when the normalized ledger itself passes financial controls.

### 6. Seller Central Monthly Transaction is a reconciliation/accounting reference source

The project shall treat Seller Central Monthly Transaction as:

```text
official posted-date reconciliation source
+ accounting/bookkeeping reference
+ manual fallback / validation source
```

It is not the Management P&L month source.

The following verified rules are frozen:

- `Released` and `Deferred` rows both belong to the posted-date monthly transaction view and must not be filtered down to Released-only;
- `Transfer` is cash movement and does not enter operating profit;
- posted-date advertising charges/refunds are bookkeeping/billing timing data;
- Ads API `report_date` spend remains the Management Operating P&L advertising expense;
- Settlement remains a separate close/cash reconciliation view.

### 7. Historical fixed cost assumptions are retired from the new default accounting pack

The old hand-built workbook used historical assumptions such as:

```text
30 RMB product cost / unit
2.5 RMB first-mile / unit
6.9 USD/CNY
```

Those values must not be silently carried forward as the default cost engine.

The new default uses the pipeline's effective-dated `amazon_sku_cost` data:

```text
product_cost
+ first_mile_cost
+ packaging_cost
+ other_unit_cost
```

If a CNY bookkeeping conversion is required, the monthly FX rate must be explicitly provided/configured and displayed. The pipeline must not silently hard-code `6.9` as a permanent accounting rate.

### 8. Adjustment/reimbursement quantity does not automatically create another COGS charge

The historical manual SOP treated Adjustment quantity as inventory loss by default and could therefore subtract product/first-mile cost again.

The new default policy is conservative:

```text
normal Shipment product units -> costed
verified liquidation/removal units -> costed
Adjustment / reimbursement quantity -> no automatic extra COGS
```

An Adjustment/reimbursement may only create additional inventory cost when there is explicit evidence that the event represents a distinct inventory loss not already captured by the normalized cost lifecycle.

**Amendment 2026-08-18:** `WAREHOUSE_LOST` is the explicit supported exception. Under ADR-018 it is written off only after Finances reimbursement amount, FBA Reimbursements reason/SKU/quantity/currency and effective-date landed cost all reconcile. Ordinary return/reversal reimbursements still do not create duplicate COGS. Any ambiguity fails closed and applies no automatic inventory-loss cost.

### 9. Default presentation uses explicit minus signs

All financial workbooks must show negative values with an explicit `-` sign, for example:

```text
-$114.89
-7.85%
```

Negative meaning must not rely on red font or accounting parentheses alone.

### 10. Legacy sheets stop being default presentation artifacts

The following historical functions are no longer required as separate default sheets in the management workbook:

- detailed Settlement buckets;
- amount-category raw expansions;
- Ads timing sheet as a standalone primary sheet;
- raw metadata;
- journal-entry proposal sheet;
- quarter rollup;
- standalone FX sheet;
- source-document index;
- payout reconciliation;
- adjustment detail sheet.

Their underlying data/audit evidence is not deleted. Where still useful, it remains in JSON, normalized tables, logs, or the compact accountant/reconciliation workbook.

## Consequences

Positive:

- management receives a report optimized for decisions instead of implementation detail;
- accounting receives a smaller, traceable workbook aligned with bookkeeping categories;
- both artifacts use the same normalized financial core, reducing presentation-driven formula drift;
- manual Monthly Transaction exports remain useful for validation without becoming an automation dependency;
- historical fixed-cost assumptions and Adjustment double-cost risk are removed from the default flow;
- international-market expansion can reuse the separation between operating view, bookkeeping view and cash/Settlement view.

Trade-offs:

- the report writer and delivery layer must produce two XLSX artifacts instead of one all-in-one workbook;
- some historical users may need the JSON/audit data when they want the removed technical sheets;
- a CNY accountant view requires an explicit monthly FX input/configuration if CNY conversion is requested;
- manual Seller Central reconciliation remains an operational validation step when a source export is provided.

## Implementation boundary / current state

The v2.0 presentation redesign is implemented and production-validated. No database migration was required. The legacy all-in-one XLSX remains generated for compatibility, while default monthly delivery attaches the separate Operating Report and Accountant Workbook.

ADR-018 adds the only current accounting-hardening formula extension: a **verified warehouse-lost inventory write-off** is deducted separately from Management Operating Profit and the accountant posted-month reference profit. This does not change the natural-month Finances source, Ads report-date source, Settlement Close positioning, or Product Gross Margin definition.

## Related documents

- `docs/adr/ADR-015-natural-month-management-pnl.md`
- `docs/adr/ADR-018-warehouse-lost-inventory-writeoff.md`
- `docs/features/feature_monthly_reporting_pack_redesign.md`
- `docs/features/feature_monthly_financial_close_report.md`
- `docs/features/feature_monthly_executive_pnl_landed_cogs.md`
- `docs/features/feature_sku_cost_management.md`
- `docs/data_access/seller_central_manual_exports.md`
