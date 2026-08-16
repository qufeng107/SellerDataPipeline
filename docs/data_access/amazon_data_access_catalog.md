# Amazon 数据接入总目录

> 更新时间：2026-08-10  
> 文档定位：SellerDataPipeline 的 Amazon 数据接入总览。本文只回答“能从哪里拿到什么原始数据，以及当前取样/解析状态如何”。业务功能设计见 `docs/features/`；当前真实数据库结构见 `docs/database/database_current_schema_spec.md`。

## 1. 接入范围总览

当前项目将 Amazon 数据源分为三类：

| 数据源 | 主要获取方式 | 原始文件/响应结构 | 当前状态 | 正式子文档 |
|---|---|---|---|---|
| SP-API Reports | `createReport` / `getReports` / `getReportDocument`；settlement 使用 Amazon-generated report discovery | TSV/TXT flat file 或 report-specific JSON | 核心经营、库存、订单、财务、促销和库存流水类报告已完成取样；其中主要报告已真实入库并通过幂等验证 | [`sp_api_reports_catalog.md`](sp_api_reports_catalog.md) |
| SP-API Finances v2024-06-19 | `listTransactions` | JSON transactions / items / contexts / recursive breakdowns | v1.89 live reconciliation completed；v1.90-v1.90.3 normalized natural-month ledger + Management P&L production verified；May/Jun/Jul Seller Central reconciliation、COGS/FNSKU identity、idempotency 均通过 | [`../features/feature_finances_api_natural_month_ledger.md`](../features/feature_finances_api_natural_month_ledger.md) |
| Amazon Ads API | Profiles API + Reporting v3 create/status/download | JSON top-level array；profile response JSON | US Ads profile 已发现；4 类 Sponsored Products 日报已真实入库并验证幂等性；`spPurchasedProduct` 当前样例为空 | [`amazon_ads_reports_catalog.md`](amazon_ads_reports_catalog.md) |
| Seller Central 手动导出 | 后台页面手工下载 CSV/TSV/XLSX | 取决于页面和报表 | 当前仅作为 fallback 和人工补充路径，不作为第一优先自动化路径 | [`seller_central_manual_exports.md`](seller_central_manual_exports.md) |

## 2. 当前已知数据接入清单

| 数据/报告 | 来源 | 格式 | 当前样例行数 | 当前接入状态 |
|---|---|---|---:|---|
| `GET_COUPON_PERFORMANCE_REPORT` | SP-API Reports | `json` | 2 | real ingestion verified |
| `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | SP-API Reports | `delimited` | 8 | real ingestion verified |
| `GET_FBA_INVENTORY_PLANNING_DATA` | SP-API Reports | `delimited` | 4 | sampled + analyzed |
| `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | SP-API Reports | `delimited` | 5 | real ingestion verified |
| `GET_FBA_REIMBURSEMENTS_DATA` | SP-API Reports | `delimited` | 19 | real ingestion verified |
| `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | SP-API Reports | `delimited` | 112 | real ingestion verified |
| `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` | SP-API Reports | `delimited` | 0 | sampled header-only / empty |
| `GET_LEDGER_DETAIL_VIEW_DATA` | SP-API Reports | `delimited` | 207 | real ingestion verified |
| `GET_LEDGER_SUMMARY_VIEW_DATA` | SP-API Reports | `delimited` | 150 | real ingestion verified |
| `GET_MERCHANT_LISTINGS_ALL_DATA` | SP-API Reports | `delimited` | 6 | real ingestion verified |
| `GET_PROMOTION_PERFORMANCE_REPORT` | SP-API Reports | `json` | 1 | real ingestion verified |
| `GET_RESERVED_INVENTORY_DATA` | SP-API Reports | `delimited` | 5 | sampled + analyzed |
| `GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT` | SP-API Reports | `delimited` | 5 | sampled + analyzed |
| `GET_SALES_AND_TRAFFIC_REPORT` | SP-API Reports | `json` | 6 | real ingestion verified |
| `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | SP-API Reports | `delimited` | 4911 | real ingestion verified |
| `GET_STRANDED_INVENTORY_UI_DATA` | SP-API Reports | `not_sampled` | n/a | current account returned cancelled/no-data in sampling; no sample document yet |
| `GET_FBA_RECOMMENDED_REMOVAL_DATA` | SP-API Reports | `not_sampled` | n/a | current account returned cancelled/no-data in sampling; no sample document yet |
| `GET_FBA_STORAGE_FEE_CHARGES_DATA` | SP-API Reports | `not_sampled` | n/a | current sampling window returned cancelled/no-data |
| `GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA` | SP-API Reports | `not_sampled` | n/a | current sampling window returned cancelled/no-data |
| `GET_FBA_OVERAGE_FEE_CHARGES_DATA` | SP-API Reports | `not_sampled` | n/a | current sampling window returned cancelled/no-data |
| `GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA` | SP-API Reports | `not_sampled` | n/a | excluded from default sampling because it may include customer comments |
| `GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL` | SP-API Reports | `not_sampled` | n/a | excluded from default sampling because it may include buyer/contact/address fields |
| `spCampaigns` | Amazon Ads API | `json` | 8 | sampled + analyzed + real ingestion verified |
| `spTargeting` | Amazon Ads API | `json` | 99 | sampled + analyzed + real ingestion verified |
| `spSearchTerm` | Amazon Ads API | `json` | 61 | sampled + analyzed + real ingestion verified |
| `spAdvertisedProduct` | Amazon Ads API | `json` | 32 | sampled + analyzed + real ingestion verified |
| `spPurchasedProduct` | Amazon Ads API | `json` | 0 | sampled empty |

## 3. 原始文件留存约定

真实 raw file 可能包含经营数据、订单数据或财务明细，不提交 GitHub。

本地留存路径约定：

```text
reports/raw/amazon/{marketplace_id}/{report_type}/{date}/...
reports/raw/amazon_ads/{profile_id}/{report_type_id}/{date}/...
```

运行过程中的 manifest、preview 和临时文件保存到：

```text
runtime/
```

`reports/raw/` 和 `runtime/` 应保持在 `.gitignore` 中。

## 4. 脱敏样例记录来源

当前字段结构主要来自：

```text
requirements_to_be_deprecated/data_samples/*.md
```

这些文件是脱敏后的字段统计和样例分析结果，不是原始 Amazon 报表。后续迁移完成后，`docs/data_access/` 是正式目录；`requirements_to_be_deprecated/data_samples/` 暂时作为字段取样记录的历史来源；删除计划见 `docs/project/requirements_deprecation_plan.md`。

## 5. 状态定义

| 状态 | 含义 |
|---|---|
| `sampled + analyzed` | 已下载真实或可用样例，并生成字段统计。 |
| `sampled header-only / empty` | 已拿到文件结构或空数组，但当前窗口没有业务行。 |
| `discovered + sampled aggregate` | 例如 settlement，由 Amazon 自动生成，已通过 discovery 下载多份并聚合分析。 |
| `real ingestion verified` | 已完成真实 Azure SQL 写入和幂等性验证。 |
| `not_sampled` | 已列入计划或候选，但当前没有有效样例。 |
| `excluded from default sampling` | 因可能包含敏感买家/客户字段，默认不取样。 |

## 6. 与执行周期的关系

每个数据源的下载/入库频率不相同。当前建议周期记录在：

```text
docs/operations/ingestion_job_cadence_catalog.md
```

未来程序可读取 `pipeline_job_config` 表决定哪些任务到期需要运行；该表设计见：

```text
docs/features/feature_ingestion_job_config.md
```

## 7. 与功能设计的关系

本目录不决定某个数据如何入库或如何计算指标。新功能开发时，应在 `docs/features/feature_*.md` 中引用本目录的具体 report/API，并进一步说明：

```text
输入数据 -> parser -> schema guard -> repository/upsert -> 数据库表 -> 验收标准
```
