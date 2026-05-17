# Feature: Ingestion Job Configuration

> 状态：Planned  
> 更新时间：2026-05-18  
> 文档定位：设计用于记录数据下载、入库、加工和报表任务执行周期的配置表。当前先支持 manual-first 流程；未来 Azure Container Apps Jobs 可读取该配置决定调度频率。

## 1. 背景

当前核心 ingestion 已经完成手动 dry-run、execute 和幂等性验证。下一阶段需要进入利润核算和周报，但在自动化前，需要先明确：

```text
每类数据多久下载一次？
每类数据多久入库一次？
每个脚本默认回看多少天？
哪些任务只适合手动？
哪些任务未来可以自动定时？
```

这些信息不应只写在文档里，也应有数据库配置表，方便后续程序读取。

## 2. 业务目标

本功能目标：

1. 建立一个统一任务配置表，记录下载、入库、加工、报表和邮件任务。
2. 支持手动执行阶段的 checklist 和顺序管理。
3. 为未来 Azure Container Apps Jobs 提供调度配置来源。
4. 避免把执行周期硬编码在脚本或 GitHub Actions YAML 中。
5. 支持按 marketplace/profile/data_domain/report_type 管理任务。

## 3. 非目标

当前阶段不做：

1. 不直接实现自动调度器。
2. 不替代 `amazon_sync_run_log`；运行结果仍由 run log 记录。
3. 不在第一版实现复杂 cron parser。
4. 不自动发送邮件。
5. 不把业务利润口径写入本表。

## 4. 设计原则

采用两层结构：

```text
pipeline_job_config
  记录“应该如何运行”和“多久运行一次”

amazon_sync_run_log
  记录“实际运行了什么、是否成功、写了多少行”
```

也就是说：

```text
config = plan / desired state
run_log = execution / actual state
```

## 5. 目标表设计

准备新增：

```text
pipeline_job_config
```

核心字段：

| 字段 | 含义 |
|---|---|
| `job_key` | 稳定唯一任务键，例如 `manual.ingest.inventory_snapshot.us`。 |
| `job_group` | `download` / `ingest` / `process` / `report` / `email`。 |
| `job_name` | 可读名称。 |
| `source_system` | `sp_api_reports` / `amazon_ads` / `internal` / `email`。 |
| `marketplace_id` | Amazon marketplace id，例如 `ATVPDKIKX0DER`。 |
| `profile_id` | Ads profile id；非 Ads 任务可为空。 |
| `data_domain` | listing、inventory、orders、profit、weekly_report 等。 |
| `report_type` | SP-API report type 或 Ads report group。 |
| `target_table` | 主要目标表；多表任务可写 summary 或 JSON。 |
| `script_path` | 当前手动或未来自动化要调用的脚本。 |
| `default_args_json` | 默认参数 JSON。 |
| `manual_run_order` | 手动 checklist 的建议顺序。 |
| `recommended_cadence_unit` | `hour` / `day` / `week` / `month` / `on_demand`。 |
| `recommended_cadence_value` | 周期数，例如 1。 |
| `default_lookback_days` | 默认回看窗口。 |
| `data_window_lag_days` | 数据延迟安全窗口。 |
| `execution_phase` | `manual_first` / `scheduled_candidate` / `scheduled_active` / `deprecated`。 |
| `enabled` | 是否启用。 |
| `notes` | 业务说明和限制。 |

## 6. Migration 与 seed

准备新增 migration：

```text
sql/migrations/012_create_ingestion_job_config.sql
```

准备新增 seed：

```text
sql/seeds/001_seed_ingestion_job_config_core_jobs.sql
```

执行顺序建议：

```powershell
python scripts/run_sql_migration.py --file sql/migrations/012_create_ingestion_job_config.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/012_create_ingestion_job_config.sql
python scripts/run_sql_migration.py --file sql/seeds/001_seed_ingestion_job_config_core_jobs.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/seeds/001_seed_ingestion_job_config_core_jobs.sql
python scripts/export_database_schema_spec.py --output-prefix after_012_job_config --include-row-counts
```

执行成功后，需要更新：

```text
docs/database/database_current_schema_spec.md
docs/operations/ingestion_job_cadence_catalog.md
docs/project/progress_next_steps.md
```

## 7. 第一批 seed 任务范围

第一批配置包括：

```text
Ads ingestion
Listing ingestion
Inventory ingestion
Sales & Traffic ingestion
Settlement ingestion
Orders ingestion
FBA Reimbursements ingestion
FBA Fee Preview ingestion
Promotion/Coupon ingestion
Inventory Ledger ingestion
Profit calculation placeholder
Weekly report placeholder
Email report placeholder
```

其中 Profit、Weekly Report 和 Email 仍为 planned，不应自动执行。

## 8. 后续自动化使用方式

未来 Azure Container Apps Jobs 可以按以下逻辑读取配置：

```text
WHERE enabled = 1
  AND execution_phase IN ('scheduled_candidate', 'scheduled_active')
```

然后结合 `amazon_sync_run_log` 判断：

```text
上次成功时间
当前是否超过 cadence
是否需要补跑 lookback window
是否有失败需要告警
```

当前阶段仍先用表作为人工 checklist 和未来自动化准备，不急于开发 scheduler。

## 9. 验收标准

本功能完成的最低标准：

1. `012_create_ingestion_job_config.sql` dry-run 成功。
2. `012_create_ingestion_job_config.sql` 在 Azure SQL 执行成功。
3. seed 执行成功且重复执行不会重复插入。
4. `pipeline_job_config` 行数符合第一批任务清单。
5. `database_current_schema_spec.md` 来自 live schema 结果并同步更新。
6. cadence catalog 与 seed 表保持一致。

## 10. 当前状态

截至 2026-05-18：

```text
设计完成
012 migration 已准备，尚未执行
seed 已准备，尚未执行
scheduler 未开发
```
