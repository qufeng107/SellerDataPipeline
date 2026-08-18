# ADR-018: Verified Warehouse-Lost Inventory Write-off

- Status: Accepted / implemented locally, pending Azure golden validation
- Date: 2026-08-18
- Decision scope: monthly Management P&L, accountant workbook, FBA reimbursement reconciliation
- Depends on: ADR-015 Natural-Month Management P&L, ADR-016 Separate Monthly Operating Report and Accountant Workbook

## Context

July 2026 reconciliation against Seller Central Monthly Transaction showed that `FBAInventoryReimbursement` contains materially different economic events. Normal return/reversal reimbursements should not create another COGS charge merely because Amazon reports a quantity. A verified `WAREHOUSE_LOST` reimbursement is different: Amazon has compensated a unit that was physically lost in FBA inventory, so the inventory asset may also require a cost write-off.

The Finances natural-month row contains the recognized reimbursement amount, but the July `WAREHOUSE_LOST` row does not reliably carry SKU/quantity unit events. The FBA Reimbursements report contains the supporting reason, Seller SKU/FNSKU, cash/inventory reimbursement quantities and reimbursement amount.

A blanket rule in either direction is unsafe:

```text
all reimbursements -> cost again       # double-COGS risk
all reimbursements -> never cost again # misses a real warehouse-loss write-off
```

## Decision

### 1. Finances remains the monetary source of truth

A warehouse-loss accounting event starts only when the marketplace-local Finances ledger contains a management-included `FBAInventoryReimbursement` whose normalized description identifies both `WAREHOUSE` and `LOST`.

The Finances amount is the recognized reimbursement income. FBA Reimbursements detail is a supporting identity/quantity source, not a replacement monetary ledger.

### 2. Automatic write-off requires complete verification

The pipeline may automatically apply warehouse-lost inventory cost only when all of the following pass:

1. Finances warehouse-lost reimbursement amount is positive.
2. Same-month FBA Reimbursements contains warehouse-lost detail.
3. FBA reimbursement amount reconciles to the Finances warehouse-lost amount within USD 0.01.
4. Currency is consistent with the monthly ledger.
5. A positive cash-reimbursed quantity can be identified.
6. Seller SKU or FNSKU can be identified.
7. SKU identity resolves unambiguously using the existing direct-cost-first / unique-FNSKU fallback policy.
8. Effective-date `amazon_sku_cost` exists for every unit being written off.

If any condition fails, status is `needs_review`, the normal sharing/send gate must remain closed, and **no candidate warehouse-loss cost is automatically applied to profit**. Candidate row-level costs may remain visible only for diagnosis.

### 3. Cash reimbursement and inventory replacement are not treated the same

```text
quantity_reimbursed_cash      -> eligible for verified inventory-cost write-off
quantity_reimbursed_inventory -> no automatic P&L write-off because Amazon replaced the unit
```

A positive amount with no inventory replacement may use `quantity_reimbursed_total` as a guarded fallback only when a positive cash quantity is otherwise absent.

### 4. Normal reimbursements still do not create duplicate COGS

`REVERSAL_REIMBURSEMENT`, customer-return reimbursement and other non-warehouse-loss reimbursement quantities do not automatically create another COGS charge.

### 5. Product Gross Margin stays a product-economics metric

Normal `Landed COGS` continues to cover sales + verified liquidation/removal units only:

```text
Product Gross Margin
= (Product Sales - Sales/Liquidation Landed COGS) / Product Sales
```

Warehouse-lost inventory write-off is shown as a separate operating cost. It does not distort Product Gross Margin.

### 6. Management Operating Profit includes verified warehouse loss separately

When verification succeeds:

```text
Management Operating Profit
= Natural-Month Finances operating net before ads replacement
- Ads API report-date spend
- Sales/Liquidation Landed COGS
- Verified Warehouse-Lost Inventory Write-off
```

### 7. Accountant reference profit uses the same verified inventory-loss treatment

```text
Posted-Month Reference Profit
= Amazon transaction net excluding Transfer
- Sales/Liquidation Landed COGS
- Verified Warehouse-Lost Inventory Write-off
```

The reimbursement income remains visible separately from the inventory-loss cost so the accountant can trace both sides of the event.

### 8. Accountant workbook is Chinese-first bilingual

Accounting-facing labels, explanations, source headers and control notes must use detailed Chinese-first bilingual wording. `OK` must be described as a **data-validation status**, not accountant approval.

The workbook must explicitly distinguish:

- Product sales units;
- Sales + liquidation costed units;
- Warehouse-lost units;
- Finances lifecycle source-row count versus Seller Central Monthly Transaction row count;
- posted-date Amazon advertising billing versus Ads API report-date management spend;
- Settlement close/cash reference versus monthly bookkeeping transactions.

## Consequences

Positive:

- avoids both reimbursement double-COGS and missed warehouse-loss inventory expense;
- preserves the already verified Finances monetary ledger;
- makes inventory-loss accounting independently traceable by reimbursement ID/SKU/quantity/cost;
- fails closed instead of applying partial or guessed COGS;
- keeps Product Gross Margin comparable across months.

Trade-offs:

- Monthly Financial Close now reads FBA Reimbursements detail in addition to its existing summary context;
- a verified warehouse-loss month can change Management Operating Profit relative to the pre-ADR-018 baseline;
- missing FBA reimbursement detail or missing SKU cost will block normal report sharing until resolved.

## Migration / schema impact

```text
No migration required.
```

The existing `amazon_fba_reimbursement` and `amazon_sku_cost` tables already contain the required fields.

## Validation

Local unit coverage must prove at minimum:

- verified `WAREHOUSE_LOST` produces one separate landed-cost write-off;
- normal reimbursement produces no inventory write-off;
- missing detail / amount mismatch / currency mismatch / SKU-cost gap fails closed;
- sales/liquidation Landed COGS remains unchanged by warehouse loss;
- Management Operating Profit and accountant reference profit deduct the verified loss exactly once.

Azure golden validation must rerun May/June/July before production rollout because historical months may contain warehouse-loss events not included in the previous profit baseline.
