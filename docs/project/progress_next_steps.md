# SellerDataPipeline 当前进展与下一步计划

> 更新时间：2026-05-18  
> 当前版本：v1.54 data coverage audit implemented; ready for 2026 YTD backfill planning  
> 文档定位：记录项目真实进展、已完成里程碑、当前非阻塞问题和下一步开发顺序。本文不承载详细字段设计；功能细节见 `docs/features/`。

## 1. 当前一句话状态

核心 Amazon SP-API / Ads normalized ingestion 已完成，Promotion/Coupon 和 Inventory Ledger 也已补齐并通过真实 Azure SQL execute + 第二次 execute 幂等性验证。项目现在应从“继续扩 ingestion”转向：

```text
手动运营流程
-> 任务周期配置已落库
-> 利润核算口径已冻结
-> SKU 成本模板导出/导入
-> 数据覆盖审计
-> 利润 preview/周报/月报生成
-> 邮件发送
-> Azure Container Apps Jobs 自动化
```

## 2. 已完成真实入库闭环

| 数据域 | 入口 | 目标表 | 验收结果 |
|---|---|---|---|
| Ads | Amazon Ads SP reports | 4 张 Ads daily 表 | `sync_run_id=1/2`; inserted=200; second run updated=200 |
| Listing | `GET_MERCHANT_LISTINGS_ALL_DATA` | `amazon_listing_snapshot` | inserted=6; second run updated=6 |
| Inventory snapshot | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | `amazon_inventory_daily` | inserted=5; second run updated=5 |
| Sales & Traffic | `GET_SALES_AND_TRAFFIC_REPORT` | `amazon_sales_traffic_daily`, `amazon_sales_traffic_asin_daily` | `sync_run_id=7/8`; inserted=7; second run updated=7 |
| Settlement | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | `amazon_settlement_transaction` | `sync_run_id=9/10`; inserted=4911; second run updated=4911 |
| Orders | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | `amazon_order_item` | `sync_run_id=11/12`; inserted=112; second run updated=112 |
| FBA Reimbursements | `GET_FBA_REIMBURSEMENTS_DATA` | `amazon_fba_reimbursement` | `sync_run_id=13/14`; inserted=19; second run updated=19 |
| FBA Fee Preview | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | `amazon_fba_fee_preview` | `sync_run_id=15/16`; inserted=8; second run updated=8 |
| Promotion/Coupon | Promotion + Coupon reports | 4 张 Promotion/Coupon 表 | `sync_run_id=17/18`; inserted=10; second run updated=10 |
| Inventory Ledger | Ledger summary + detail reports | `amazon_inventory_ledger_summary_daily`, `amazon_inventory_ledger_detail` | `sync_run_id=19/20`; inserted=357; second run updated=357 |

## 3. 数据库状态

已执行成功的 migration：

```text
001_create_core_tables.sql
002_create_indexes.sql
003_add_listing_snapshot_business_key_hash.sql
004_add_inventory_daily_business_key_hash.sql
005_add_sales_traffic_business_key_hashes.sql
006_add_settlement_transaction_business_key.sql
007_add_order_item_business_key.sql
008_add_fba_reimbursement_business_key.sql
009_add_fba_fee_preview_business_key.sql
010_add_promotion_coupon_business_keys.sql
011_add_inventory_ledger_business_keys.sql
012_create_ingestion_job_config.sql
```

Seed 已执行成功：

```text
001_seed_ingestion_job_config_core_jobs.sql
```

当前真实数据库记录在：

```text
docs/database/database_current_schema_spec.md
```

`runtime/schema_exports/after_012_job_config.md/json` 显示当前用户表数量为 29，`pipeline_job_config` 当前 13 行。

## 4. 已完成基础设施

| 能力 | 状态 |
|---|---|
| Azure SQL connection warm-up retry | 已实现，默认 max_attempts=6 |
| Firewall/IP allowlist 错误识别 | 已实现，40615 fail fast |
| `check_database_status.py` | 已实现 |
| `export_database_schema_spec.py` | 已实现 |
| schema guard | 已在各 ingestion 链路使用 |
| dry-run preview | 已在各 ingestion 链路使用 |
| repository MERGE/upsert | 已在各 ingestion 链路使用 |
| updated-files-only 交付模式 | 当前默认工作方式 |
| GitHub Action lint/test | 已修复最近的 Ruff 与 pytest 问题 |

## 5. 新增 operations 文档

本轮新增：

```text
docs/operations/manual_execution_workflow.md
docs/operations/ingestion_job_cadence_catalog.md
docs/features/feature_ingestion_job_config.md
docs/project/core_ingestion_completion_review.md
docs/project/requirements_deprecation_plan.md
```

对应 ADR：

```text
docs/adr/ADR-007-manual-first-before-automation.md
docs/adr/ADR-008-ingestion-job-config-table.md
```

## 6. requirements_to_be_deprecated 状态

当前结论：暂不直接删除。

原因：仍有文档和历史 sample notes 引用 `requirements_to_be_deprecated/data_samples/*.md`。该目录已经不是正式设计来源，但仍作为历史取样证据保留。

正式清理计划见：

```text
docs/project/requirements_deprecation_plan.md
```

## 7. 当前非阻塞限制

| 限制 | 后续处理 |
|---|---|
| raw file registry 关联仍不完整，部分 `source_raw_file_id` 可能为 NULL | 后续补 raw file registry / Blob Storage 归档增强。 |
| 任务周期已写入 `pipeline_job_config` | 后续 profit/report/email placeholder 待对应功能实现后再启用。 |
| 利润核算口径已冻结 | 已采用 Settlement-led Financial Profit v1.0；下一步开发手动利润 preview。 |
| SKU 成本、采购成本、头程/海运成本需要录入机制 | 已实现 xlsx 模板导出/导入脚本，目标表为 `amazon_sku_cost`。 |
| 2026-01-01 至今各数据源覆盖范围尚需确认 | 已新增 `scripts/audit_data_coverage.py`，先跑 coverage audit，再决定 backfill 范围。 |
| 周报/月报脚本未实现 | 数据覆盖和利润 preview 人工复核稳定后开发手动周报/月报。 |
| 自动邮件和 Azure Jobs 未实现 | 手动流程稳定后再自动化。 |

## 8. 下一步建议

利润核算口径已冻结在：

```text
docs/features/feature_profit_calculation.md
docs/adr/ADR-009-settlement-led-profit-policy.md
```

当前冻结规则：

```text
财务利润以 Settlement 为主；
Orders / Sales & Traffic / Ads / Promotion-Coupon 只做运营解释和差异分析；
SKU 成本来自 amazon_sku_cost；
第一版采用 SKU 标准成本 + 生效日期；
第一版先输出人工复核文件，不立即新增利润结果表。
```

下一批建议先运行 `scripts/audit_data_coverage.py --target-start-date 2026-01-01`，确认每个 normalized 数据源实际覆盖范围；再按缺口补 2026 年初至今的 raw data / ingestion；核心源覆盖后，继续运行利润 preview 并用 3月/4月或 5月上旬数据人工复核。

## 9. 当前建议手动运行顺序

参考：

```text
docs/operations/manual_execution_workflow.md
docs/operations/ingestion_job_cadence_catalog.md
```

短期规则：

```text
先手动下载 raw data
-> 手动运行各 ingestion CLI
-> 手动检查数据库
-> 手动导出/导入 SKU 成本
-> 手动运行数据覆盖审计
-> 手动生成利润 preview / 周报
-> 人工复核邮件
-> 最后才上自动化 Jobs
```
