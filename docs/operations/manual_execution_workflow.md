# Manual Execution Workflow

> 更新时间：2026-05-18  
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
-> 报表生成
-> 人工复核
-> 邮件发送
```

后续 Azure Container Apps Jobs 只是把这些已验收命令按配置定时运行，并补充审计、告警和失败重试。

## 2. 手动运行总流程

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

具体 report type 和建议周期见：

```text
docs/operations/ingestion_job_cadence_catalog.md
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

### 2.5 数据加工与报表生成

下一阶段将新增利润核算和周报命令。预期手动流程是：

```powershell
python scripts/calculate_profit_report.py --marketplace-id ATVPDKIKX0DER --period weekly --start-date YYYY-MM-DD --end-date YYYY-MM-DD
python scripts/generate_weekly_operations_report.py --marketplace-id ATVPDKIKX0DER --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

以上脚本尚未实现，正式设计见后续：

```text
docs/features/feature_profit_calculation.md
docs/features/feature_weekly_operations_report.md
```

### 2.6 人工复核与邮件发送

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

未来 Azure Container Apps Jobs 应读取数据库中的 job config 或等价配置，决定：

```text
运行哪个脚本
多久运行一次
使用哪个 marketplace/profile
回看几天数据
失败后如何告警
```

对应设计见：

```text
docs/features/feature_ingestion_job_config.md
sql/migrations/012_create_ingestion_job_config.sql
```
