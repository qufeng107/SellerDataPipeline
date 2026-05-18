# Ingestion Job Cadence Catalog

> 更新时间：2026-05-19  
> 文档定位：记录每类数据下载、入库、刷新窗口和后续加工任务的建议周期。本文用于指导手动执行顺序和未来自动化 Jobs 调度，不替代 feature 文档。

## 1. 已冻结原则

当前采用：

```text
Overlapping rolling refresh + normalized upsert + weekly-or-longer analysis
```

含义：

```text
数据刷新可以每 1-2 天执行一次；
每次下载一段多日窗口，窗口之间故意重叠；
入库使用 MERGE/upsert 覆盖同一 business key；
销售周报、广告周报、利润周报/月报等分析产物最短周期为一周。
```

详细规则见：

```text
docs/operations/data_refresh_policy.md
docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md
```

## 2. 数据刷新与分析加工分离

不要把“刷新数据”理解成“生成日报”。项目当前明确分为：

| 类型 | 作用 | 建议频率 |
|---|---|---|
| Core data refresh | 滚动补数、更新最近数据、吸收回填/归因变化 | 每 1-2 天 |
| Weekly analysis | 销售周报、广告周报、利润周报、库存周报 | 每周 |
| Monthly/accounting analysis | 月度利润、会计口径复核 | 每月或会计需要时 |
| Email/report delivery | 发送人工复核后的报告 | 周报/月报确认后 |

因此可以每 2 天刷新 Sales/Traffic、Orders、Ads，但不生成每日正式经营结论。

## 3. 核心数据项建议周期

| 数据域 | 数据源 / Report | 当前入库脚本 | 刷新频率 | 默认刷新窗口 | Stable lag | 分析产物频率 | 数据延迟/注意事项 |
|---|---|---|---:|---:|---:|---:|---|
| Ads SP core | `spCampaigns` / `spTargeting` / `spSearchTerm` / `spAdvertisedProduct` | `scripts/ingest_ads_reports.py` | 每 2 天 | 14 天 | 3 天 | 周报/活动复盘 | 广告归因会回填，广告周报不直接使用今天/昨天作为最终结论。 |
| Listing snapshot | `GET_MERCHANT_LISTINGS_ALL_DATA` | `scripts/ingest_listing_snapshot.py` | 每周；改 listing 后立即跑 | 当前快照 | 0 天 | 周报参考 | 主要是 SKU/ASIN/listing 状态快照，小体量店铺每周足够。 |
| Inventory snapshot | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | `scripts/ingest_inventory_snapshot.py` | 每 2 天或周报前 | 当前快照 | 0 天 | 周报 | 周报“还剩多少货”的首要来源。 |
| Sales & Traffic | `GET_SALES_AND_TRAFFIC_REPORT` | `scripts/ingest_sales_traffic_report.py` | 每 2 天 | 10 天 | 2 天 | 周报 | 销售/流量可能延迟；正式周报默认使用 stable cutoff。 |
| Settlement | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | `scripts/ingest_settlement_report.py` | 每周 discovery/ingest | 60 天 | 0 天 | 周报/月报利润 | Amazon 自动生成，重点是 discovery 新 settlement report。利润财务主口径。 |
| Orders | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | `scripts/ingest_orders_report.py` | 每 2 天 | 10 天 | 2 天 | 周报 | 用于订单/SKU/促销 ID 辅助分析；不作为财务收入主口径。 |
| FBA Reimbursements | `GET_FBA_REIMBURSEMENTS_DATA` | `scripts/ingest_fba_reimbursements_report.py` | 每周 | 60 天 | 7 天 | 周报/月报异常解释 | 赔偿可能滞后出现，建议回看更长窗口。 |
| FBA Fee Preview | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | `scripts/ingest_fba_fee_preview_report.py` | 每周或费用变更前后 | 当前快照 | 0 天 | 周报参考 | 预估费用用于参考；最终费用仍以 settlement 实扣为准。 |
| Promotion/Coupon | `GET_PROMOTION_PERFORMANCE_REPORT` / `GET_COUPON_PERFORMANCE_REPORT` | `scripts/ingest_promotion_coupon_reports.py` | 活动期每 2 天；非活动期每周 | 30 天或活动期 | 2 天 | 周报/活动复盘 | 用于分析优惠券、价格折扣、会员日/Prime Day 活动表现。 |
| Inventory Ledger | `GET_LEDGER_SUMMARY_VIEW_DATA` / `GET_LEDGER_DETAIL_VIEW_DATA` | `scripts/ingest_inventory_ledger_reports.py` | 每周；库存异常时按需 | 30 天 | 3 天 | 周报异常解释 | 不是库存余额首要来源，用于解释库存变化和审计异常。 |
| SKU cost management | SKU universe + `amazon_sku_cost` | `scripts/export_sku_cost_template.py` / `scripts/import_sku_cost_template.py` | 进货/成本变化/复核前 | 全量 SKU 模板 | n/a | 周报/月报成本基础 | 通过 xlsx 模板导出/导入维护内部 SKU 标准成本。 |
| Profit calculation | Settlement + `amazon_sku_cost` + auxiliary normalized tables | `scripts/calculate_profit_report.py` | 每周/月报前 | 报表周期 | 2 天 | 周报/月报 | 已冻结 Settlement-led Financial Profit v1.0；缺成本默认阻塞正式净利润。 |
| Weekly operations report | normalized SQL tables + profit result | planned | 每周 | 上一自然周 | 2 天 | 周报 | 第一版生成后人工复核，再考虑邮件自动化。 |
| Email report delivery | generated report files | planned | 每周确认后 | n/a | n/a | 周报/月报 | 第一阶段不直接自动发送正式邮件。 |

## 4. 手动执行建议节奏

### 4.1 每 2 天核心刷新

```text
Ads SP core：最近 14 天
Sales & Traffic：最近 10 天
Orders：最近 10 天
Promotion/Coupon：活动期最近 30 天或整个活动期
Inventory snapshot：当前快照
```

这一步只是刷新 normalized 数据，不生成正式日报。

### 4.2 每周固定完整刷新与审计

```text
Settlement discovery/ingest：最近 60 天
FBA Reimbursements：最近 60 天
Inventory Ledger：最近 30 天
FBA Fee Preview：当前快照
Listing snapshot：当前快照
Data coverage audit：检查 stable cutoff
Profit preview：上一自然周或指定周
Weekly operations report：人工复核后生成
```

### 4.3 月报/会计复核前

```text
Ads：额外刷新最近 30-45 天
Settlement：确认最近 60 天 discovery 完整
FBA Reimbursements：刷新最近 60 天
Promotion/Coupon：覆盖活动期
SKU Cost：确认成本覆盖所有销售 SKU
Data coverage audit：按月度窗口复核
Profit preview：月度周期
```

## 5. 当前数据库配置表

当前已新增并 seed：

```text
pipeline_job_config
```

该表当前记录 13 条任务配置，包括 10 个核心 ingestion 任务和 3 个利润/周报/邮件任务。字段包括：

```text
job_key
job_group
script_path
recommended_cadence_unit
recommended_cadence_value
default_lookback_days
data_window_lag_days
execution_phase
enabled
```

已执行：

```text
sql/migrations/012_create_ingestion_job_config.sql
sql/seeds/001_seed_ingestion_job_config_core_jobs.sql
```

本策略新增待执行/可重复执行 seed：

```text
sql/seeds/002_update_ingestion_job_config_refresh_policy.sql
```

执行后配置表会与本 catalog 的重叠刷新策略一致。

## 6. 重要边界

Cadence catalog 只是调度建议，不等于业务指标口径：

- 财务利润仍以 Settlement 为主。
- Orders / Sales & Traffic / Ads / Promotion-Coupon 只用于运营解释和周报分析。
- 周报库存余额用 `amazon_inventory_daily`。
- 库存变化解释用 Inventory Ledger。
- FBA Fee Preview 是预估，最终费用以 Settlement 为准。
- 每 2 天刷新数据不代表生成日报；分析产物最短周期是一周。
