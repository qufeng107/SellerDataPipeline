# Feature: Finances API Natural-Month Ledger + Management P&L

> 状态：Production verified；v1.90-v1.90.3 rollout complete  
> 版本：v1.90.3  
> 更新时间：2026-08-10  
> 数据库影响：新增 migration `016_create_finances_natural_month_ledger.sql`。  
> 报表影响：Monthly Financial Close 升级到 `v1.5-natural-month-finances`；Settlement Close 保留独立口径。

## 1. 冻结结论

v1.89 live reconciliation 已在 Amazon US 真实账户上完成 2026-05 / 2026-06 / 2026-07 三个月验证。Seller Central Monthly Transaction 可由 Finances API 在 **America/Los_Angeles 本地自然月**下稳定还原：

```text
Orders       = DEFERRED_RELEASED Shipment
Zero-$ units = RELEASED Shipment(amount=0)（COGS unit only；不进 revenue/order total）
Refunds      = RELEASED Refund
Liquidation  = DEFERRED + DEFERRED_RELEASED RemovalShipment
Ads charge   = RELEASED ProductAdsPayment（只作 Amazon posted-charge reference）
Service Fee  = RELEASED ServiceFee
Reimburse    = RELEASED FBAInventoryReimbursement
Adjustment   = RELEASED MiscellaneousLedgerAdjustment
Transfer     = RELEASED Transfer（只作现金/结算 reference，不进经营利润；保留 API 原始符号）
```

已验证自然月总额：

```text
2026-05 Orders       1915.68
2026-05 Refunds      -355.95
2026-05 Liquidation     2.30

2026-06 Orders       2184.16
2026-06 Refunds      -380.50
2026-06 Liquidation     0.55

2026-07 Orders       1097.24
2026-07 Refunds      -209.00
2026-07 Liquidation     2.08
```

2026-07 进一步用 UTC/PDT boundary audit 证明，原始 UTC month 多出的 Shipment `35.90` 与 Refund `-22.00` 全部来自 `UTC_2026-07 -> LOCAL_2026-06`，因此 marketplace timezone 是财务月份的一部分，不允许用 UTC calendar month 直接归属。

## 2. 数据模型

migration 016 新增：

```text
dbo.amazon_finance_transaction
```

业务幂等键：

```text
marketplace_id + transaction_id
-> SHA-256 business_key_hash
```

同一个 Finances API transaction 后续从 deferred/released lifecycle 发生状态变化时，更新同一行，不新增 duplicate transaction。

表保留：

- transaction id/status/type/description；
- UTC posted time；
- marketplace local posted datetime/date/timezone；
- amount/currency；
- settlement/order/deferred/release identifiers；
- explicit lifecycle role / management include flag；
- key transaction breakdown totals；
- ServiceFee 细分：subscription / coupon / deal / storage / customer-return / other；
- SKU unit events JSON；
- complete raw transaction JSON + raw SHA256；
- business key hash + timestamps。

## 3. Ingestion

新增：

```text
scripts/ingest_finances_natural_month.py
```

默认 dry-run：

```bash
python scripts/ingest_finances_natural_month.py \
  --marketplace-id ATVPDKIKX0DER \
  --month 2026-07
```

正式执行：

```bash
python scripts/ingest_finances_natural_month.py \
  --marketplace-id ATVPDKIKX0DER \
  --month 2026-07 \
  --execute
```

API fetch window 会按 marketplace local month 前后各扩一天，再严格按 local posted date 过滤，避免 UTC 边界漏/错归。

输出审计：

```text
runtime/ingestion/finances_api/{marketplace}/{YYYY-MM}/
  raw_pages.json
  prepared_rows.json
  summary.json
```

## 4. Guard policy

本版不把未知 transaction/status 自动塞进利润：

```text
known current-period lifecycle -> explicit include
known prior-period release     -> explicit exclude/reference
Transfer                       -> cash reference only
ProductAdsPayment              -> Amazon posted Ads reference only
unknown non-zero combination   -> review_required + SQL execute blocked
```

已知但不进入当前自然月经营金额口径的组合包括：

```text
RELEASED Shipment (non-zero)
DEFERRED_RELEASED Refund
RELEASED RemovalShipment
```

这些在三个月真实对账中对应 previous-period release timing，不应重复计入当前自然月金额。

v1.90 Gate 2 又发现一个必须单独处理的零金额商品事件：2026-06 Seller Central 有 120 个 Order units，但 Finances 的 `DEFERRED_RELEASED Shipment` 只有 118 units。逐单核查确认剩余 2 units 分别来自两笔 `RELEASED Shipment amount=0`，Finances API 本身保留了正确 SKU + `quantityShipped=1`。因此 v1.90.1 冻结规则为：**零金额 RELEASED Shipment 不加入 revenue/order total，但其完整 ProductContext unit event 进入 natural-month landed COGS**。若 SKU/quantity 不完整，仍 `review_required` 并阻止 SQL execute。

## 5. Management P&L

Management Operating P&L 不再使用 Settlement sales/refund/fee posted-date 混合口径。

新公式：

```text
Natural-month operating net
  = selected Finances API operating transactions
  - Transfer
  - ProductAdsPayment posted-charge reference

Management Operating Profit
  = Natural-month operating net
  - Ads API report-date spend
  - Natural-month landed COGS
```

其中 COGS unit events 来自 selected `Shipment` / `RemovalShipment` 的 item ProductContext SKU + quantity，并额外包含 v1.90.1 已验证的 `RELEASED Shipment amount=0` COGS-only unit；继续使用 `amazon_sku_cost` 的 effective-date 成本。金额 inclusion 与 COGS-unit inclusion 明确分离。

v1.90.2 增加 **FNSKU -> canonical Seller SKU cost identity resolution**。Finances 的 liquidation/removal transaction 可能把 FNSKU 放在 `ProductContext.sku`，且不返回 ASIN；此时成本解析顺序冻结为：

```text
1. source SKU 直接命中 amazon_sku_cost -> 直接使用，永远优先
2. source SKU 无直接成本 -> 在 amazon_inventory_daily 中按 FNSKU 查历史身份
3. 截至目标月末只有 1 个唯一 Seller SKU -> 使用该 canonical Seller SKU 的 effective-date 成本
4. FNSKU 对应多个 Seller SKU、无映射、或 canonical SKU 无有效成本 -> fail closed / needs_review
```

identity query 只读取 `snapshot_date <= target month end` 的库存快照，不使用未来月份身份；同一 FNSKU 即使存在多个 ASIN 观察值，只要 canonical Seller SKU 唯一即可解析。报告 JSON 额外记录 `cost_identity_resolutions`（例如 `X004WU7DSH->SC-9HC3-5TFL`），便于审计。

Settlement 继续独立输出：

```text
Settlement Close Profit = Settlement posted-date net - Settlement-period landed COGS
```

两者不互相覆盖。

## 6. Monthly automation

`monthly collect_ingest` 新增：

```text
Ingest Finances natural-month ledger
```

位置在 Ads ingestion 后、Settlement ingestion 前。新表未迁移或出现 non-zero unknown lifecycle 时，任务 fail closed。

Monthly report 增加 reconciliation check：

```text
finances_natural_month_coverage
```

以下任一情况阻止正常分享：

- month ledger 为空；
- unknown non-zero lifecycle/type；
- 纳入经营口径的 Shipment / RemovalShipment 无法完整提取 item-level SKU + quantity；
- natural-month SKU COGS 未全覆盖；
- extracted unit count 与 costed unit count 不一致。

## 7. Azure Gate 与生产验收

截至 2026-08-10 全部完成：

```text
Gate 1  migration 016 + schema postcheck                         PASS
Gate 2  May/Jun/Jul natural-month amount + unit dry-run          PASS
Gate 3A first execute backfill: 227 + 264 + 161 = 652 rows       PASS
Gate 3B second execute: inserted=0; total rows still 652          PASS
Gate 4  May/Jun/Jul report preview + full COGS coverage           PASS
Gate 5  v1.90.2 business smoke; audit tail bug isolated           PASS business / audit bug found
Gate 6  v1.90.3 final production smoke                            PASS
```

v1.90.2 Gate 4 最终 cost identity：

```text
May  X004Q3AKFX -> HU-4XAJ-PYLD -> USD 6.94 all-in
July X004WU7DSH -> SC-9HC3-5TFL -> USD 4.17 + first-mile 0.5271
```

最终 Monthly Financial Close：

| Month | Product Sales | Landed COGS | Management Operating Profit | Margin | Settlement Close Profit |
|---|---:|---:|---:|---:|---:|
| 2026-05 | 2316.38 | 467.25 | 548.35 | 23.67% | 39.02 |
| 2026-06 | 2870.06 | 573.05 | 612.70 | 21.35% | 1130.93 |
| 2026-07 | 1464.14 | 291.23 | -114.89 | -7.85% | 444.55 |

v1.90.3 production image：

```text
ghcr.io/qufeng107/seller-data-pipeline:2fa19ad316720742d1871765fa0c1149c6b9fb9a
```

July production smoke：

```text
execution=sdp-monthly-collect-ingest-cbacfwp
status=Succeeded
Finances local_rows=161 review_required=0
Finances attempted=161 inserted=0 updated=161
Settlement attempted=1628 inserted=0 updated=1628
Automation commands=11 failed=0
artifact_save scanned=169 saved=169 skipped=0
```

v1.90.3 同时修复 automation audit 对 Finances list-root JSON artifact 的兼容性；业务命令成功后不再因为合法 JSON array 的 `.get()` 解析假设导致 execution 尾部失败。

正式 monthly `collect_ingest` 已移除 `--continue-on-error`，恢复 fail-closed。历史 2026-05/06/07 邮件不 `force-resend`。

## 8. 本地验收

```text
v1.90.2: `PYTHONPATH=src pytest -q -> 370 passed`
v1.90.3: `PYTHONPATH=src pytest -q -> 371 passed`
`python -m compileall -q src scripts tests -> passed`
ruff -> 本地环境未安装；CI Safety lint 不绕过
```
