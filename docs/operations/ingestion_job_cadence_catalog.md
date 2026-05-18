# Ingestion Job Cadence Catalog

> 更新时间：2026-05-18  
> 文档定位：记录每类数据下载、入库和后续加工任务的建议周期。本文用于指导手动执行顺序和未来自动化 Jobs 调度，不替代 feature 文档。

## 1. 设计原则

不同 Amazon 数据源更新频率不同，不能全部用同一个周期：

- 库存快照、广告、订单、销售流量适合高频更新。
- Settlement 是 Amazon 周期性生成，适合定期 discovery，不适合按固定日期强行 createReport。
- FBA Fee Preview、Reimbursements、Inventory Ledger 适合周度或按需更新。
- Promotion/Coupon 在活动期间应高频更新，非活动期可以降低频率。
- 周报/月报加工依赖 normalized 数据先完成，不应和 raw data 下载混在一个不可拆分任务里。

## 2. 核心数据项建议周期

| 数据域 | 数据源 / Report | 当前入库脚本 | 建议手动周期 | 未来自动化建议 | 默认回看窗口 | 数据延迟/注意事项 |
|---|---|---|---|---|---:|---|
| Ads SP core | `spCampaigns` / `spTargeting` / `spSearchTerm` / `spAdvertisedProduct` | `scripts/ingest_ads_reports.py` | 每周至少 1 次；广告调整期每日 | 每日 | 7-14 天 | 广告归因会回填，自动化应滚动更新最近 7-14 天。 |
| Listing snapshot | `GET_MERCHANT_LISTINGS_ALL_DATA` | `scripts/ingest_listing_snapshot.py` | 每周 1 次；改 listing 后立即跑 | 每日或每周 | 1 天 | 主要是 SKU/ASIN/listing 状态快照。小体量店铺每周足够。 |
| Inventory snapshot | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | `scripts/ingest_inventory_snapshot.py` | 每日或每周报表前 | 每日 | 1 天 | 周报“还剩多少货”的首要来源。 |
| Sales & Traffic | `GET_SALES_AND_TRAFFIC_REPORT` | `scripts/ingest_sales_traffic_report.py` | 每周至少 1 次 | 每日 | 7 天 | 销售/流量可能延迟，建议滚动更新最近 7 天。 |
| Settlement | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | `scripts/ingest_settlement_report.py` | 每周 1 次 | 每日 discovery 或每周 | 30-60 天 | Amazon 自动生成，重点是 discovery 新 settlement report。利润财务口径优先来源。 |
| Orders | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | `scripts/ingest_orders_report.py` | 每周至少 1 次 | 每日 | 7 天 | 用于订单/SKU/促销 ID 辅助分析；注意隐私字段 guard。 |
| FBA Reimbursements | `GET_FBA_REIMBURSEMENTS_DATA` | `scripts/ingest_fba_reimbursements_report.py` | 每周 1 次 | 每周 | 30 天 | 赔偿可能滞后出现，建议回看更长窗口。 |
| FBA Fee Preview | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | `scripts/ingest_fba_fee_preview_report.py` | 每周或费用变更前后 | 每周 | 1 天 | 预估费用用于参考；最终费用仍以 settlement 实扣为准。 |
| Promotion/Coupon | `GET_PROMOTION_PERFORMANCE_REPORT` / `GET_COUPON_PERFORMANCE_REPORT` | `scripts/ingest_promotion_coupon_reports.py` | 活动期间每日；非活动期每周 | 活动期间每日，平时每周 | 30 天或活动期 | 适合分析百分比折扣、固定 Coupon、会员日/Prime Day 活动表现。 |
| Inventory Ledger | `GET_LEDGER_SUMMARY_VIEW_DATA` / `GET_LEDGER_DETAIL_VIEW_DATA` | `scripts/ingest_inventory_ledger_reports.py` | 每周 1 次；库存异常时按需 | 每周 | 7-14 天 | 不是库存余额首要来源，用于解释库存变化和审计异常。 |
| SKU cost management | SKU universe + `amazon_sku_cost` | implemented / manual | 每次进货、成本变化或利润复核前 | 按需 | 全量 SKU 模板 | 通过 xlsx 模板导出/导入维护内部 SKU 标准成本。 |
| Profit calculation | Settlement + `amazon_sku_cost` + auxiliary normalized tables | planned / policy frozen | 每周/月报前 | 每周/月度 | 报表周期 | 已冻结 Settlement-led Financial Profit v1.0；缺成本默认阻塞正式净利润。 |
| Weekly operations report | normalized SQL tables + profit result | planned | 每周手动生成 | 每周 | 上一自然周 | 第一版生成后人工复核，再考虑邮件自动化。 |
| Email report delivery | generated report files | planned | 人工发送 | 周报确认后自动草稿/发送 | n/a | 第一阶段不直接自动发送正式邮件。 |

## 3. 手动执行建议节奏

小体量店铺当前建议：

```text
每日可选：Inventory snapshot、Ads、Sales & Traffic、Orders
每周固定：全部核心 ingestion + Profit + Weekly Report
活动期间：Promotion/Coupon 每日
库存异常：Inventory Ledger 按需加跑
Settlement：每周检查，未来自动化可每日 discovery
```

## 4. 当前数据库配置表

为了让程序自动判断任务周期，当前已新增并 seed：

```text
pipeline_job_config
```

该表当前记录 13 条任务配置，包括 10 个核心 ingestion 任务和 3 个利润/周报/邮件 placeholder。该表记录：

```text
job_key
job_group
script_path
default_args_json
recommended_cadence_unit
recommended_cadence_value
default_lookback_days
data_window_lag_days
execution_phase
enabled
```

设计文档：

```text
docs/features/feature_ingestion_job_config.md
```

已执行的 migration / seed：

```text
sql/migrations/012_create_ingestion_job_config.sql  # 4/4 batches
sql/seeds/001_seed_ingestion_job_config_core_jobs.sql  # 1/1 batch
```

## 5. 重要边界

Cadence catalog 只是调度建议，不等于业务指标口径。比如：

- 周报库存余额用 `amazon_inventory_daily`。
- 库存变化解释用 Inventory Ledger。
- 促销效果看 Promotion/Coupon，但最终财务扣款以 Settlement 为准。
- FBA Fee Preview 是预估，最终费用以 Settlement 为准。
