# Feature: Finances API Natural-Month Sampling

> 状态：Completed / production live reconciliation passed; superseded by v1.90 ledger  
> 版本：v1.89  
> 更新时间：2026-08-09  
> 数据库影响：无 migration；只新增 read-only Finances API client + raw sampling/analyzer。  
> 报表影响：**本版本不切换 Monthly Financial Close 口径。**

## 1. 背景

2026-05 至 2026-07 Seller Central `Monthly Transaction` 与 Settlement V2 对账确认：

- Settlement V2 适合 settlement close / cash reconciliation，但它是 Amazon 自动生成并按 posted/released timing 进入月度；
- 自然月经营分析不能继续把 Settlement posted-date sales/refund/FBA/promotion 与 report-date Ads 混成一个 Management P&L；
- 2026-07 还观察到 Seller Central 已出现 `settlement_id=27207351391`，但 Settlement V2 `getReports` 暂未发现对应自动生成 report，说明 settlement maturity 与经营月份存在天然时间差。

Amazon Finances API v2024-06-19 提供 `GET /finances/2024-06-19/transactions`，可按 `postedAfter` / `postedBefore` / marketplace / transaction status 获取 transaction，并返回 transaction status、transactionId、postedDate、totalAmount、relatedIdentifiers、items、contexts、breakdowns 等结构。

v1.89 **先取真实样本，不直接切换财务口径**。这是为了遵守“先 sample/reconcile，再冻结 schema/mapping”的项目规则，避免仅凭文档猜测 breakdownType 与 Seller Central Monthly Transaction 各列的对应关系。

官方参考：

- https://developer-docs.amazon.com/sp-api/docs/finances-api-v2024-06-19-reference
- https://developer-docs.amazon.com/sp-api/reference/listtransactions
- https://developer-docs.amazon.com/sp-api/lang-US/docs/get-latest-transactions

## 2. 冻结范围

### 2.1 Client capability

`AmazonSpApiClient.list_finance_transactions(...)` 使用：

```text
GET /finances/2024-06-19/transactions
```

支持：

```text
postedAfter
postedBefore
marketplaceId
transactionStatus
relatedIdentifierName / relatedIdentifierValue
nextToken
```

分页请求保留原 filter 并增加 `nextToken`。默认不设置 `transactionStatus`，用于真实样本阶段观察：

```text
DEFERRED
RELEASED
DEFERRED_RELEASED
```

### 2.2 Read-only sampling

新增：

```text
scripts/sample_finances_transactions.py
```

示例：

```bash
python scripts/sample_finances_transactions.py \
  --marketplace-id ATVPDKIKX0DER \
  --month 2026-07
```

输出路径：

```text
runtime/sampling/finances_api/{marketplace_id}/{start}_{end}/
  pages/page_001.json
  pages/page_002.json
  ...
  transactions.json
  summary.json
```

这些文件属于 raw financial data，`runtime/` 已被 `.gitignore` 排除，禁止提交 Git。

### 2.3 Bounded pagination

默认 `max_pages=100`。如果 Amazon 仍返回 `nextToken`，但达到上限，则 fail closed：

```text
RuntimeError: pagination exceeded max_pages
```

禁止静默生成 partial sample。

### 2.4 Recent-window guard

Amazon 要求 `postedBefore` 至少早于请求时间约 2 分钟。若目标结束时间过新，sampler 会将 effective `postedBefore` 保守截到 `now - 2m05s`，并在 summary 标记：

```text
posted_before_was_clamped = true
```

历史完整自然月（例如 2026-07）不会触发该截断。

## 3. Schema / breakdown exploration

本版 analyzer 不定义会计 category，也不写 SQL。

`summary.json` 只做结构性观察：

```text
transaction_count
unique_transaction_id_count
duplicate_transaction_ids
status_counts
transaction_type_counts
description_counts
related_identifier_name_counts
settlement_ids
total_amounts_by_currency
total_amounts_by_transaction_type_currency
total_amounts_by_status_currency
observed_transaction_keys
observed_item_keys
observed_context_types
observed_breakdown_types
breakdown_leaf_totals
```

`breakdown_leaf_totals` 递归展开 transaction/item breakdown tree，只汇总 leaf amount，并保留完整路径，例如：

```text
transaction:<parent>/<child>|USD
item:<parent>/<child>|USD
```

这样可以在真实 sample 中观察 Amazon 的实际 `breakdownType`，而不是预先猜测 `Product Sales / FBA Fee / Promotion / Advertising` 的 API 名称。

## 4. 日志输出规则

CLI 不打印完整 transaction，避免 Azure Log Analytics 出现大量财务明细。

只输出：

```text
FINANCES_SAMPLE ...
FINANCES_SAMPLE_COMBINED=...
FINANCES_SAMPLE_SUMMARY_PATH=...
FINANCES_SAMPLE_SUMMARY_JSON={compact summary}
```

compact summary 默认只包含绝对金额最大的前 30 个 breakdown leaf totals。

## 5. 本版明确非目标

v1.89 sampling 阶段**不做**：

- 不新增 `amazon_finance_transaction` 表；
- 不写 Azure SQL；
- 不修改 `MonthlyFinancialSummary`；
- 不把 Monthly Management P&L 从 Settlement 切到 Finances API；
- 不把 Settlement Close P&L 删除；
- 不自动把 API breakdownType 映射为 Seller Central Monthly Transaction CSV columns；
- 不将该 sampler 直接加入正式 monthly `collect_ingest`，避免 Finance and Accounting role 未授权时阻断稳定生产 pipeline。

## 6. Production sampling gate

部署后第一步只运行 2026-07 read-only sample。

成功条件：

1. API 权限可用；如 403，先检查 SP-API developer profile / app registration 的 **Finance and Accounting** role，不修改现有 Settlement pipeline。
2. 完整分页结束，未达到 `max_pages`。
3. summary 中 marketplace/currency/transaction IDs 无明显异常。
4. 将 sample 与 Seller Central `2026JulMonthlyTransaction.csv` 对账：至少验证 transaction types、settlement IDs、transaction statuses、root totals、主要 breakdown paths。
5. 只有在 5/6/7 三个月 reconciliation 能稳定解释后，才进入下一版 normalized ledger / Management P&L migration。

## 7. 下一阶段候选（尚未实现）

若 live reconciliation 通过，再设计：

```text
Finances API raw transactions
        -> immutable normalized financial ledger
        -> natural-month accounting categories
        -> Management Operating P&L

Settlement V2
        -> Settlement Close P&L / cash reconciliation
```

其中两套 ledger 必须通过 `SETTLEMENT_ID` / `ORDER_ID` / transaction IDs 做 reconciliation，而不是互相覆盖。

## 8. 本地验收

```text
PYTHONPATH=src pytest -q
python -m compileall -q src scripts tests
ruff check src scripts tests
```

v1.89 新 regression 覆盖：

- Finances API endpoint/version/filter 参数；
- nextToken 分页必须保留原 filter；
- transaction status validation；
- multi-page raw artifacts；
- recent postedBefore clamp；
- max_pages fail closed；
- recursive breakdown leaf summary；
- duplicate transactionId visibility。


## 9. Production reconciliation result (2026-08-09)

US live sampling passed. May/June/July Orders, Refunds and Liquidations reconciled exactly after `America/Los_Angeles` local-month filtering and lifecycle split. v1.90 productionization is documented in `feature_finances_api_natural_month_ledger.md`.
