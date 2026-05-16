# Feature: Azure SQL 数据库基础设施

> 文档状态：正式功能文档  
> 负责人：AI assisted / Zifei 复核  
> 更新时间：2026-05-16  
> 功能状态：Implemented  
> 相关数据接入文档：不直接依赖外部数据源；为所有 ingestion 功能提供数据库底座  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关规则文档：`docs/database/database_migration_policy.md`、`docs/adr/ADR-002-do-not-edit-executed-migrations.md`

---

## 1. 功能摘要

本功能负责为 SellerDataPipeline 建立 Azure SQL 数据库基础设施，包括连接配置、migration 执行、当前 schema 记录、数据库状态检查和后续 schema 变更治理规则。它不直接处理 Amazon 原始报表，但为 SP-API Reports、Amazon Ads API、后续利润核算和周期报表提供统一结构化数据仓库。

当前该功能已完成第一阶段验收：Azure SQL `amazon_ops` 可连接，`001_create_core_tables.sql` 和 `002_create_indexes.sql` 已执行成功，数据库中存在 28 张用户表，`scripts/check_database_status.py` 可输出表行数、最新 sync run 和最新 schema validation event。针对 Azure SQL serverless 长时间 idle 后首次连接可能 login timeout 的情况，连接层已新增 retry + `SELECT 1` warm-up，业务 SQL 只会在连接预热成功后执行。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| Azure SQL 连接配置 | 已完成 |
| 本地连接测试 | 已完成 |
| 初始核心表 migration | 已执行 |
| 初始索引 migration | 已执行 |
| 当前 schema spec | 已完成第一版 |
| 数据库检查脚本 | 已完成 |
| Azure SQL connection warm-up retry | 已完成 |
| 单元测试 | 已完成 |
| 文档同步 | 已完成本功能文档第一版 |

功能整体状态：`Implemented`。

## 3. 业务目标

本功能服务于公司小体量跨境电商运营的长期数据底座建设。它的业务价值是：

1. 把原本分散在 Amazon Seller Central、SP-API、Ads API、Excel 和手工核算中的数据，统一沉淀到 Azure SQL。
2. 为利润核算、广告优化、库存监控、清仓决策、周报/月报提供稳定数据来源。
3. 通过 migration 和 current schema spec，保证后续 AI 迭代不会误把“未来设计”当成“真实数据库状态”。
4. 降低运维复杂度：当前公司体量较小，不需要大型数据湖，Azure SQL 足以支撑第一阶段运营分析。

## 4. 范围与非范围

### 4.1 本功能包含

- Azure SQL 连接字符串构造。
- SQL password auth 本地开发模式。
- Entra managed identity cloud job 模式的连接字符串支持。
- migration 文件拆分 `GO` batch 并执行。
- 初始核心表 `001_create_core_tables.sql`。
- 初始索引 `002_create_indexes.sql`。
- 数据库连接诊断和用户表清单。
- 数据库状态检查脚本。
- 当前真实数据库 schema spec 文档维护。
- migration 不可回改规则。

### 4.2 本功能不包含

- 不负责 Amazon SP-API 或 Ads API 的鉴权和下载。
- 不负责具体 report parser。
- 不负责某个业务功能的字段映射。
- 不负责利润公式、周报内容或清仓策略。
- 不负责 Azure Container Apps Jobs 的部署和定时调度；这是后续独立功能。
- 不负责 Azure Key Vault；后续上云时可新增功能文档或 ADR。

## 5. 输入数据

本功能的输入不是 Amazon 业务报表，而是配置、SQL 文件和运行环境。

| 来源 | 输入 | 格式 | 当前状态 | 备注 |
|---|---|---|---|---|
| `.env` | Azure SQL 连接参数 | 环境变量 | 已验证 | 本地开发当前使用 SQL password auth。 |
| `sql/migrations/001_create_core_tables.sql` | 初始核心表结构 | T-SQL | 已执行 | 29/29 batches。 |
| `sql/migrations/002_create_indexes.sql` | 初始索引 | T-SQL | 已执行 | 54/54 batches。 |
| Azure SQL | `amazon_ops` database | SQL Azure | 已验证 | 当前 28 张用户表。 |
| ODBC Driver | `ODBC Driver 18 for SQL Server` | Native driver | 本地已可用 | pyodbc 依赖该驱动。 |
| Connection warm-up | `SELECT 1` | SQL | 已实现 | 所有 `get_connection()` 在 yield 给业务 SQL 前都会执行。 |

关键 `.env` 项：

```env
AZURE_SQL_SERVER='tcp:<server>.database.windows.net,1433'
AZURE_SQL_DATABASE='amazon_ops'
AZURE_SQL_AUTH_MODE='sql_password'
AZURE_SQL_USERNAME='<username>'
AZURE_SQL_PASSWORD='<password>'
AZURE_SQL_DRIVER='ODBC Driver 18 for SQL Server'
AZURE_SQL_ENCRYPT='yes'
AZURE_SQL_TRUST_SERVER_CERTIFICATE='no'
AZURE_SQL_CONNECTION_TIMEOUT='30'
AZURE_SQL_CONNECT_MAX_ATTEMPTS='4'
AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS='5'
AZURE_SQL_CONNECT_RETRY_BACKOFF='1.8'
AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID=''
```

## 6. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Azure SQL database | `amazon_ops` | 项目主结构化数据仓库。 |
| Core tables | `dbo.amazon_*` | 存放 metadata、raw file、schema validation、listing、inventory、sales、settlement、ads 等数据。 |
| Indexes | `sys.indexes` | 支持业务键、查询和 upsert。 |
| Schema spec | `docs/database/database_current_schema_spec.md` | 记录真实数据库当前状态。 |
| Migration policy | `docs/database/database_migration_policy.md` | 约束后续 schema 变更流程。 |
| Status check output | `scripts/check_database_status.py` | 快速检查数据库连接、表行数和最新审计记录。 |

## 7. 处理流程

### 7.1 初始建库流程

```text
配置 .env Azure SQL 参数
  -> python scripts/test_azure_sql_connection.py --json
     connection layer retries known transient login-timeout errors and runs SELECT 1 warm-up
  -> python scripts/run_sql_migration.py --file sql/migrations/001_create_core_tables.sql --dry-run --show-batches
  -> python scripts/run_sql_migration.py --file sql/migrations/001_create_core_tables.sql
  -> python scripts/test_azure_sql_connection.py --list-tables
  -> python scripts/run_sql_migration.py --file sql/migrations/002_create_indexes.sql --dry-run --show-batches
  -> python scripts/run_sql_migration.py --file sql/migrations/002_create_indexes.sql
  -> python scripts/check_database_status.py
  -> 更新 current schema spec 和 progress
```

### 7.2 后续数据库变更流程

```text
更新对应 feature 文档
  -> 对比 docs/database/database_current_schema_spec.md
  -> 新增 sql/migrations/NNN_xxx.sql
  -> dry-run / 人工检查 batch
  -> 执行 migration
  -> 运行数据库检查脚本
  -> 更新 current schema spec
  -> 更新 progress_next_steps
```

## 8. 字段映射

本功能是数据库基础设施，不做 Amazon 源字段到业务字段的映射。具体字段映射必须写在对应功能文档中，例如：

- `docs/features/feature_ads_ingestion.md`
- 后续 `docs/features/feature_listing_snapshot_ingestion.md`
- 后续 `docs/features/feature_sales_traffic_ingestion.md`

## 9. 目标数据表设计

### 9.1 当前已存在表

当前 Azure SQL `amazon_ops` 已有 28 张用户表。完整字段、索引、数据来源见 `docs/database/database_current_schema_spec.md`。

| 领域 | 表 |
|---|---|
| Marketplace / control / audit | `amazon_marketplace`, `amazon_sync_run_log`, `amazon_report_request`, `amazon_raw_report_file`, `amazon_report_field_catalog`, `amazon_schema_validation_event`, `amazon_sku_cost` |
| Listing / sales / traffic | `amazon_listing_snapshot`, `amazon_sales_traffic_daily`, `amazon_sales_traffic_asin_daily` |
| Inventory | `amazon_inventory_daily`, `amazon_inventory_ledger_summary_daily`, `amazon_inventory_ledger_detail`, `amazon_reserved_inventory_daily`, `amazon_inventory_planning_daily` |
| Finance / order / FBA | `amazon_settlement_transaction`, `amazon_order_item`, `amazon_fba_reimbursement`, `amazon_fba_fee_preview` |
| Promotion / coupon | `amazon_promotion_performance`, `amazon_promotion_product_performance`, `amazon_coupon_performance`, `amazon_coupon_asin` |
| Amazon Ads | `amazon_ads_profile`, `amazon_ads_sp_campaign_daily`, `amazon_ads_sp_targeting_daily`, `amazon_ads_sp_search_term_daily`, `amazon_ads_sp_advertised_product_daily` |

### 9.2 当前已执行 migration

| 文件 | 状态 | 执行结果 | 后续是否允许修改 |
|---|---|---:|---|
| `sql/migrations/001_create_core_tables.sql` | executed | 29/29 batches | 否 |
| `sql/migrations/002_create_indexes.sql` | executed | 54/54 batches | 否 |

### 9.3 新 migration 需求

当前本功能自身没有必须立即新增的 migration。已知非阻塞优化见第 18 节。

## 10. 幂等性设计

### 10.1 Migration 幂等性

初始 migration 使用以下模式降低重复执行风险：

- 建表：`IF OBJECT_ID('dbo.table_name', 'U') IS NULL`
- 建索引：`IF NOT EXISTS (SELECT 1 FROM sys.indexes ...)`
- seed 数据：先检查目标记录是否存在。

注意：虽然 SQL 尽量可重复执行，但项目规则仍然要求**已执行 migration 不允许修改**。重复执行只能用于恢复或确认，不应用于演进结构。

### 10.2 数据检查脚本安全性

`check_database_status.py` 只读取：

- 连接诊断。
- 用户表清单。
- 表行数。
- 最新 sync run。
- 最新 schema validation event。

该脚本不写数据库。动态表名经过严格校验，只允许字母、数字和下划线组成的表名。

## 11. Schema guard 与异常处理

本功能不执行业务 report schema guard，但提供承载 schema guard 结果的数据库表：

| 表 | 用途 |
|---|---|
| `amazon_schema_validation_event` | 存储 report schema 检查结果，包括 observed/expected/missing/new/unmapped fields、requires_review、message。 |
| `amazon_report_field_catalog` | 后续用于沉淀 report 字段目录。 |

连接和 migration 异常处理：

| 场景 | 处理方式 | 是否阻塞 |
|---|---|---|
| 缺少 Azure SQL 环境变量 | `ConfigurationError` | 是 |
| 未安装 `pyodbc` | `ConfigurationError`，提示安装依赖和 ODBC Driver | 是 |
| Azure firewall 未放行 | 连接测试失败 | 是 |
| migration 某 batch 执行失败 | 当前 run 报错；不要继续后续 migration | 是 |
| 运行 `002` 前 `001` 未完成 | 可能出现目标表不存在导致索引失败 | 是 |

## 12. 审计与可追溯性

本功能创建并使用以下审计基础表：

| 审计对象 | 表/字段 | 说明 |
|---|---|---|
| 任务运行 | `amazon_sync_run_log` | 记录 job、status、started_at、finished_at、duration_ms、rows_read、rows_written、rows_skipped、rows_failed、message、error。 |
| 原始文件 | `amazon_raw_report_file` | 设计用于记录 raw file path、hash、文件大小、行列数等；当前 Ads ingestion 尚未完全写入该表。 |
| Schema 检查 | `amazon_schema_validation_event` | 记录 report schema guard 结果。 |
| 字段目录 | `amazon_report_field_catalog` | 设计用于沉淀不同 report 的字段观察结果；当前后续待完善。 |

## 13. 命令行入口

### 13.1 连接测试

```bash
python scripts/test_azure_sql_connection.py --json
python scripts/test_azure_sql_connection.py --list-tables
python scripts/test_azure_sql_connection.py --json --max-attempts 5 --retry-delay-seconds 5
```

连接层默认会重试以下类型的连接/预热错误：`08001`、`08S01`、`HYT00`、`HYT01`、`40613`、`40197`、`40501`。这些主要覆盖 Azure SQL serverless 恢复、登录超时、暂时不可用和服务忙。认证错误、SQL 语法错误、业务 SQL 错误不在这里重试。

### 13.2 Migration

```bash
python scripts/run_sql_migration.py --file sql/migrations/001_create_core_tables.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/001_create_core_tables.sql

python scripts/run_sql_migration.py --file sql/migrations/002_create_indexes.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/002_create_indexes.sql
```

### 13.3 数据库状态检查

```bash
python scripts/check_database_status.py
python scripts/check_database_status.py --json
python scripts/check_database_status.py --all-tables
python scripts/check_database_status.py --table amazon_ads_sp_campaign_daily --table amazon_sync_run_log
```

参数说明：

| 参数 | 是否必需 | 默认值 | 说明 |
|---|---|---|---|
| `--json` | 否 | false | 输出 JSON，便于 AI 或自动化脚本读取。 |
| `--limit` | 否 | 10 | 最新 sync/schema 记录数量。 |
| `--all-tables` | 否 | false | 统计所有用户表行数。 |
| `--table` | 否 | 默认重点表 | 指定要统计的表，可重复传入。 |

## 14. 相关代码路径

| 类型 | 路径 | 说明 |
|---|---|---|
| Azure SQL connection | `src/seller_data_pipeline/db/connection.py` | 构建连接字符串、retry 打开 pyodbc 连接、执行 `SELECT 1` warm-up、运行连接诊断、列出用户表。 |
| Compatibility re-export | `src/seller_data_pipeline/db/azure_sql.py` | 对外重新导出连接相关函数。 |
| Migration engine | `src/seller_data_pipeline/db/migrations.py` | 拆分 SQL Server `GO` batches 并执行 migration。 |
| Migration CLI | `scripts/run_sql_migration.py` | 运行单个 SQL migration 文件。 |
| Connection CLI | `scripts/test_azure_sql_connection.py` | 检查 Azure SQL 连接与表清单。 |
| Status CLI | `scripts/check_database_status.py` | 检查重点表行数和最新审计记录。 |
| Core schema | `sql/migrations/001_create_core_tables.sql` | 初始核心表。 |
| Indexes | `sql/migrations/002_create_indexes.sql` | 初始索引。 |
| Unit tests | `tests/unit/db/test_connection.py` | 连接字符串和配置测试。 |
| Unit tests | `tests/unit/db/test_migrations.py` | `GO` batch 拆分和 migration 执行测试。 |
| Unit tests | `tests/unit/scripts/test_check_database_status.py` | 数据库检查脚本 SQL 构造与安全性测试。 |

## 15. 测试计划

默认单元测试不应依赖真实 Azure SQL。

```bash
PYTHONPATH=src pytest -q tests/unit/db/test_connection.py
PYTHONPATH=src pytest -q tests/unit/db/test_migrations.py
PYTHONPATH=src pytest -q tests/unit/scripts/test_check_database_status.py
PYTHONPATH=src pytest -q
python -m compileall -q scripts src tests
```

手工/集成验证需要真实 Azure SQL：

```bash
python scripts/test_azure_sql_connection.py --json
python scripts/test_azure_sql_connection.py --list-tables
python scripts/check_database_status.py
```

## 16. 验收标准

本功能第一阶段已通过以下验收：

1. `python scripts/test_azure_sql_connection.py --json` 成功返回 `database_name=amazon_ops`、`server_name=amazon-ops-sql`、`edition=SQL Azure`。
2. `001_create_core_tables.sql` 执行成功：29/29 batches。
3. 执行 `001` 后，用户表数量为 28。
4. `002_create_indexes.sql` 执行成功：54/54 batches。
5. `python scripts/test_azure_sql_connection.py --list-tables` 可列出 28 张用户表。
6. `scripts/check_database_status.py` 已实现，可检查重点表行数、最新 run log、最新 schema validation event。
7. `docs/database/database_current_schema_spec.md` 已记录当前真实数据库结构。
8. `docs/database/database_migration_policy.md` 已记录后续 migration 规则。
9. Azure SQL 长时间 idle 后首次连接 timeout 的场景已通过连接层 retry + warm-up 处理，避免自动化脚本在数据库恢复过程中直接失败。

## 17. 当前实现状态

| 日期 | 进展 | 证据/命令 | 备注 |
|---|---|---|---|
| 2026-05-16 | Azure SQL 连接成功 | `python scripts/test_azure_sql_connection.py --json` | `database=amazon_ops`, `tables=0`。 |
| 2026-05-16 | 初始核心表创建成功 | `python scripts/run_sql_migration.py --file sql/migrations/001_create_core_tables.sql` | 29/29 batches。 |
| 2026-05-16 | 用户表清单验证成功 | `python scripts/test_azure_sql_connection.py --list-tables` | 28 张用户表。 |
| 2026-05-16 | 初始索引创建成功 | `python scripts/run_sql_migration.py --file sql/migrations/002_create_indexes.sql` | 54/54 batches。 |
| 2026-05-16 | 数据库检查脚本完成 | `scripts/check_database_status.py` | 输出连接、表行数、latest sync/schema events。 |
| 2026-05-16 | Azure SQL connection warm-up retry 完成 | `src/seller_data_pipeline/db/connection.py` | 处理 serverless idle/resume 后首次 login timeout；业务 SQL 前执行 `SELECT 1`。 |
| 2026-05-16 | 正式功能文档完成第一版 | `docs/features/feature_azure_sql_foundation.md` | 本文档。 |

## 18. 后续优化

- 给 `amazon_sync_run_log` 新增 `rows_inserted`、`rows_updated`，使数据库审计能记录 upsert 细分结果；当前 CLI 已能打印，但数据库表未单独保存。
- 让 Ads ingestion 和后续 SP-API ingestion 正式写入 `amazon_raw_report_file`，再把 `raw_file_id` 外键写入 schema validation event 和 normalized 表。
- 后续上 Azure Container Apps Jobs 时，将 `AZURE_SQL_AUTH_MODE` 切换或扩展到 managed identity，并引入 Key Vault/Secret 管理规则。
- 后续需要时新增 `docs/database/database_field_naming_conventions.md`，统一字段命名、金额精度、日期字段和 source 字段规范。

## 19. 弃置记录

| 日期 | 弃置内容 | 原因 | 替代方案 |
|---|---|---|---|
| 2026-05-16 | 把 GitHub Actions 作为长期业务调度器 | 不适合作为稳定业务任务调度；密钥和运行窗口治理较弱 | 后续使用 Azure Container Apps Jobs。 |
| 2026-05-16 | 修改已执行的 `001/002/003` migration 来演进 schema | 会破坏真实数据库历史和仓库一致性 | 任何变化新增 `004_xxx.sql`、`005_xxx.sql`。 |
