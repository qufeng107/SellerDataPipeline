# Manual Execution Workflow

> 更新时间：2026-05-19  
> 文档定位：本文件定义当前阶段的手动运行流程。目标是在上自动化 Jobs 前，先把每一步都做成可人工执行、可复查、可重复、可审计。

## 1. 当前阶段定义

项目当前不应直接进入全自动调度。正确阶段是：

```text
Manual-first operations
```

也就是先保证每个业务能力都能通过命令行手动完成：

```text
数据下载
-> 数据入库
-> 数据加工
-> SKU 成本维护
-> 报表生成
-> 人工复核
-> 邮件发送
```

后续 Azure Container Apps Jobs 只是把这些已验收命令按配置定时运行，并补充审计、告警和失败重试。

## 2. 手动运行总流程

### 2.0 数据刷新与分析节奏

当前冻结规则是：

```text
数据刷新可以每 1-2 天执行一次；
每次下载多日重叠窗口并通过 upsert 覆盖当前业务行；
销售周报、广告周报、利润周报/月报等分析产物最短周期是一周。
```

因此手动阶段建议分成两类动作：

```text
Core rolling refresh：每 2 天刷新 Ads / Sales & Traffic / Orders / Promotion-Coupon / Inventory snapshot。
Weekly analysis run：每周完整刷新慢源，跑 coverage audit、利润 preview 和周报。
```

详细规则见：

```text
docs/operations/data_refresh_policy.md
docs/adr/ADR-010-overlapping-refresh-weekly-analysis.md
```

### 2.1 环境检查

每次正式运行前先确认 Azure SQL 可连接：

```powershell
python scripts/test_azure_sql_connection.py --json
python scripts/check_database_status.py
```

如果遇到 Azure SQL idle/resume，连接层会自动 warm-up retry。若报 `40615 client IP not allowed`，需要先在 Azure SQL server firewall 放行当前公网 IP。

### 2.2 下载或收集 raw data

当前 raw data 仍主要保存在本地：

```text
reports/raw/amazon/{marketplace_id}/{report_type}/{date}/...
reports/raw/amazon_ads/{profile_id}/{report_type_id}/{date}/...
```

手动下载/收集阶段可使用现有脚本：

```powershell
python scripts/submit_report_requests.py ...
python scripts/collect_ready_reports.py ...
python scripts/collect_ads_reports.py ...
```

具体 report type、重叠刷新窗口和 stable cutoff 见：

```text
docs/operations/ingestion_job_cadence_catalog.md
docs/operations/data_refresh_policy.md
```

### 2.3 入库 normalized tables

每个核心数据域都有专用 ingestion CLI。默认 dry-run，不写 Azure SQL；必须显式加 `--execute` 才会写库。

建议固定顺序：

```powershell
python scripts/ingest_ads_reports.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER
python scripts/ingest_ads_reports.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_listing_snapshot.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_listing_snapshot.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_inventory_snapshot.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_inventory_snapshot.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_sales_traffic_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_sales_traffic_report.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_settlement_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_settlement_report.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_fba_reimbursements_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_fba_reimbursements_report.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_fba_fee_preview_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_fba_fee_preview_report.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_promotion_coupon_reports.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_promotion_coupon_reports.py --marketplace-id ATVPDKIKX0DER --execute

python scripts/ingest_inventory_ledger_reports.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_inventory_ledger_reports.py --marketplace-id ATVPDKIKX0DER --execute
```

手动阶段每条 ingestion 新版本首次上线时，应重复执行一次 `--execute` 验证幂等性：

```text
first execute  -> inserted > 0, updated = 0
second execute -> inserted = 0, updated > 0
```

### 2.4 入库后检查

执行：

```powershell
python scripts/check_database_status.py --all-tables
python scripts/export_database_schema_spec.py --output-prefix manual_run_check --include-row-counts
```

重点看：

```text
amazon_sync_run_log 是否有 success 记录
amazon_schema_validation_event 是否有 blocking requires_review
目标表行数是否符合预期
```

### 2.4.1 数据覆盖范围审计

在继续利润复核、周报/月报前，先运行 normalized 数据覆盖审计，确认每个数据源到底覆盖到哪一天：

```powershell
python scripts/audit_data_coverage.py --marketplace-id ATVPDKIKX0DER --target-start-date 2026-01-01
```

输出文件：

```text
runtime/data_coverage_audits/ATVPDKIKX0DER/{target_start}_{target_end}/data_coverage_audit.md
runtime/data_coverage_audits/ATVPDKIKX0DER/{target_start}_{target_end}/data_coverage_audit.csv
runtime/data_coverage_audits/ATVPDKIKX0DER/{target_start}_{target_end}/report_request_coverage.csv
```

详细规则见：

```text
docs/operations/data_coverage_audit_workflow.md
```

### 2.5 SKU 成本维护

利润 preview 依赖 `amazon_sku_cost`。该成本不是 Amazon 后台数据，而是公司内部采购、包装、头程/海运/清关/入仓分摊成本。

先导出模板：

```powershell
python scripts/export_sku_cost_template.py --marketplace-id ATVPDKIKX0DER
```

人工填写 `new_*` 列后，先 dry-run：

```powershell
python scripts/import_sku_cost_template.py --file runtime/sku_cost_templates/ATVPDKIKX0DER/sku_cost_template.xlsx
```

确认无误后 execute：

```powershell
python scripts/import_sku_cost_template.py --file runtime/sku_cost_templates/ATVPDKIKX0DER/sku_cost_template.xlsx --execute
```

详细规则见：

```text
docs/features/feature_sku_cost_management.md
```

### 2.6 数据加工与报表生成

利润核算口径已冻结为 Settlement-led Financial Profit v1.0。当前已新增利润 preview。

注意：数据可以每 1-2 天刷新，但利润、销售、广告等正式分析产物最短按周生成；不要把滚动刷新误当成日报系统。预期手动流程是：

```powershell
python scripts/audit_data_coverage.py --marketplace-id ATVPDKIKX0DER --target-start-date 2026-01-01
python scripts/calculate_profit_report.py --marketplace-id ATVPDKIKX0DER --period weekly --start-date YYYY-MM-DD --end-date YYYY-MM-DD --dry-run
python scripts/generate_weekly_operations_report.py --marketplace-id ATVPDKIKX0DER --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

`calculate_profit_report.py` 已实现；周报脚本尚未实现。利润口径已冻结，正式设计见：

```text
docs/features/feature_profit_calculation.md
docs/adr/ADR-009-settlement-led-profit-policy.md
docs/features/feature_weekly_operations_report.md  # 待创建
```

利润 preview 复核规则：

```text
Settlement 是财务主口径；
Orders / Ads / Promotion-Coupon 只做解释；
缺 SKU 成本时默认不输出正式净利润；
人工确认后再用于周报或发给会计。
```

### 2.7 人工复核与邮件发送

第一版周报不应自动发送。建议流程：

```text
生成报表文件
-> 人工打开检查利润、库存、广告、促销、异常费用
-> 确认无误后手动发送邮件
```

后续再加入：

```text
邮件草稿生成
-> 人工确认
-> 自动发送
```

## 3. 手动优先再自动化的原因

1. 当前数据口径仍在确认，尤其是利润核算、促销折扣、退款和头程成本分摊。
2. Amazon 报表存在延迟、空报告、字段漂移和 settlement 周期差异。
3. 手动流程能先暴露业务异常和数据异常，避免自动化把错误持续放大。
4. 自动化 Jobs 应复用已稳定的 CLI，不应在自动化阶段重新设计核心逻辑。

## 4. 进入自动化的条件

某个手动流程可以自动化，需要满足：

```text
CLI 已实现
默认 dry-run 安全
--execute 已通过真实写库
重复 execute 幂等性通过
sync_run_log 有记录
schema_validation_event 无 blocking error
check_database_status.py 可确认结果
相关 feature 文档和 cadence catalog 已更新
```

## 5. 与未来 Jobs 的关系

未来 Azure Container Apps Jobs 应读取当前已建立的 `pipeline_job_config` 或等价配置，决定：

```text
运行哪个脚本
多久运行一次
使用哪个 marketplace/profile
回看几天数据
失败后如何告警
```

对应设计与已执行结构见：

```text
docs/features/feature_ingestion_job_config.md
sql/migrations/012_create_ingestion_job_config.sql
sql/seeds/001_seed_ingestion_job_config_core_jobs.sql
```
