# SellerDataPipeline 当前进展与下一步计划

> 更新时间：2026-05-23  
> 当前版本：v1.69 SMTP report email sending design frozen  
> 文档定位：记录项目真实进展、已完成里程碑、当前非阻塞问题和下一步开发顺序。本文不承载详细字段设计；功能细节见 `docs/features/`。

## 1. 当前一句话状态

核心 Amazon SP-API / Ads normalized ingestion 已完成，Promotion/Coupon 和 Inventory Ledger 也已补齐并通过真实 Azure SQL execute + 第二次 execute 幂等性验证。项目现在应从“继续扩 ingestion”转向：

```text
手动运营流程
-> 任务周期配置已落库
-> 利润核算口径已冻结
-> SKU 成本模板导出/导入
-> 数据覆盖审计 + stable cutoff
-> 重叠窗口 rolling refresh
-> 月度财务结算报表 / 每周经营周报 / 广告优化周报
-> Report Delivery 邮件草稿包
-> SMTP 邮件发送设计已冻结，待实现
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

新增待执行/可重复执行 seed：

```text
002_update_ingestion_job_config_refresh_policy.sql
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
docs/operations/data_refresh_policy.md
docs/operations/ingestion_job_cadence_catalog.md
docs/operations/data_coverage_audit_workflow.md
docs/operations/historical_backfill_workflow.md
docs/operations/manual_refresh_plan_workflow.md
docs/features/feature_ingestion_job_config.md
docs/project/core_ingestion_completion_review.md
docs/project/requirements_deprecation_plan.md
```

对应 ADR：

```text
docs/adr/ADR-007-manual-first-before-automation.md
docs/adr/ADR-008-ingestion-job-config-table.md
docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md
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
| 任务周期已写入 `pipeline_job_config` | 新增 seed 002 用于把配置调整为重叠窗口刷新 + 周度分析；执行后需导出 live schema/行数并记录。 |
| 利润核算口径已冻结 | 已采用 Settlement-led Financial Profit v1.0；第一版手动利润 preview 已实现，下一步做多周期复核和周报。 |
| SKU 成本、采购成本、头程/海运成本需要录入机制 | 已实现 xlsx 模板导出/导入脚本，目标表为 `amazon_sku_cost`。 |
| 2026-03 起核心数据已完成第一轮补数 | Orders 历史 backfill 已逐 raw file 入库；Ads 历史 backfill 已入库；coverage audit 中 covers_stable_window 提升到 4。后续日常更新改用 `run_manual_refresh_plan.py`。 |
| 周报脚本已实现；月报脚本已初步复核 | Monthly Financial Close Report v1 已实现 JSON + 单个 XLSX 多 sheet 输出，且 2026-03 / 2026-04 dry-run 已初步复核；Weekly Business Review v1 已实现 JSON + 单个 XLSX 多 sheet 输出，并用 2026-05-11..2026-05-17 真实数据生成 status=ok。Ads API campaign daily 目前 5 月后可用于周度加工，3/4 月 Ads context 缺失仅作为运营解释 warning。Weekly Ads Optimization Report v1 已完成代码实现，并已用 2026-05-11..2026-05-17 真实 Ads 数据执行 live dry-run，结果 status=ok、reconciliation_warnings=0。Report Delivery / Email Pack v1 已实现草稿包生成；SMTP 真实发送 v1.1 已实现，采用 Python 标准库 `smtplib` / `EmailMessage`，收件人默认通过 Azure SQL `report_email_recipient_config` 按 `report_type + audience` 配置，runtime JSON 仅作 fallback；真实发送必须显式 `--execute`。 |
| 自动邮件和 Azure Jobs 未实现 | Report Delivery / Email Pack v1 已实现邮件草稿包生成；SMTP 真实发送 v1.1 已实现；Azure Jobs 在人工复核稳定后再实现。 |

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

当前已新增 historical backfill CLI，并已补齐 2026-03 起的 Orders 与核心经营数据；Ads campaign daily 目前 5 月后数据已可稳定用于周度加工。为避免日常操作继续变成零散命令，已新增 `scripts/run_manual_refresh_plan.py`，将标准定期更新固化为 `core_rolling` / `weekly_full` 两个 plan，以及 `submit` / `collect` / `ingest` / `audit` 四个 phase。Monthly Financial Close Report v1 已实现，默认输出 JSON + 单个 XLSX 多 sheet，不默认输出 Markdown 或多个 CSV；2026-03 / 2026-04 真实 dry-run 已初步复核，Ads API campaign daily 在 3/4 月缺失仅作为运营解释 warning，不影响 Settlement-led 财务利润。Weekly Business Review v1 已实现，默认输出 JSON + 单个 XLSX 多 sheet，并用 2026-05-11..2026-05-17 真实数据生成 status=ok。Weekly Ads Optimization Report v1 已完成代码实现，并已用同一周真实数据执行 live dry-run 验证通过。

## 9. 管理报表设计进展

当前报表体系冻结为三类：

```text
1. Monthly Financial Close Report：月度财务结算报表，偏 CFO/会计/股东汇报。
2. Weekly Business Review：每周经营周报，偏 CEO/运营负责人每周复盘。
3. Weekly Ads Optimization Report：每周广告优化报表，偏广告动作清单。
```

已完成设计：

```text
docs/features/feature_monthly_financial_close_report.md  # v1 默认输出 JSON + 单个 XLSX 多 sheet
docs/features/feature_weekly_business_review.md  # v1 默认输出 JSON + 单个 XLSX 多 sheet
docs/features/feature_weekly_ads_optimization_report.md  # v1 默认输出 JSON + 单个 XLSX 多 sheet
docs/features/feature_report_delivery_email.md  # 统一邮件草稿包 v1、SMTP 发送 v1.1、DB 收件人路由 v1.2 已实现
```

代码实现进展：Monthly Financial Close Report v1 已完成本地 unit tests/compileall，并根据真实 2026-03 / 2026-04 输出完成一轮小修补。Weekly Business Review v1 已完成代码实现、unit tests 和 compileall，默认输出 JSON + 单个 XLSX 多 sheet，并用 2026-05-11..2026-05-17 真实数据生成 status=ok。Weekly Ads Optimization Report v1 已完成代码实现，默认输出 JSON + 单个 XLSX 多 sheet，不调用 Ads 写接口。之后建议顺序：配置腾讯企业邮 SMTP 环境变量 -> `send_report_email.py --dry-run` 从 DB 校验收件人/附件/guard -> `--execute` 发送测试邮件 -> Azure Jobs。

## 10. 当前建议手动运行顺序

参考：

```text
docs/operations/manual_execution_workflow.md
docs/operations/ingestion_job_cadence_catalog.md
```

短期规则：

```text
core_rolling：每 1-2 天按 submit -> collect -> ingest -> audit 刷新核心源
weekly_full：每周按 submit -> collect -> ingest -> audit 刷新核心源 + 慢源
SKU 成本：按需通过 xlsx 模板维护
周报/月报：只在 stable coverage audit 后生成
邮件发送：Report Delivery v1 已可生成草稿包；SMTP v1.1/v1.2 已实现，先用 `send_report_email.py --dry-run` 校验，再使用 `--execute` 发送
Azure Jobs：复用 run_manual_refresh_plan.py 的固定 plan，不另起一套逻辑
```

注意：数据刷新可以 1-2 天一次，但销售/广告/利润等正式分析产物最短周期为一周。


### 2026-05-23 — Report Delivery DB recipient routing implemented

- Executed `sql/migrations/013_create_report_email_recipient_config.sql` successfully against Azure SQL, 3/3 batches.
- Executed `sql/seeds/003_seed_report_email_recipient_config_initial.sql` successfully, 2/2 batches.
- Exported live schema to `runtime/schema_exports/azure_sql_schema_20260523_213026.md/json`.
- Updated `docs/database/database_current_schema_spec.md` to v1.14 with `report_email_recipient_config`.
- Implemented DB recipient lookup in `send_report_email.py`; default `--recipient-source db`, optional `json` or `auto`.
- Initial DB recipients: `feng@cuidena.cn`, `yufei@cuidena.cn`, `qian@cuidena.cn`.
