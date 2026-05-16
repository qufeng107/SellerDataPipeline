# SellerDataPipeline

SellerDataPipeline 是一个面向小体量跨境电商公司的 Amazon 运营数据管道项目。项目第一阶段聚焦美国 Amazon Seller Central、SP-API Reports 与 Amazon Ads API，把销售、库存、结算、广告、促销等数据沉淀到 Azure SQL，后续用于利润核算、广告优化、库存监控、清仓决策、周报/月报与自动化运营分析。

当前项目不做 Django/Web 后台；核心形态是：

```text
Amazon SP-API / Amazon Ads API / Seller Central raw exports
  -> local raw files and manifests
  -> parser
  -> schema guard
  -> repository upsert
  -> Azure SQL
  -> reporting / analysis / scheduled jobs
```

## 当前真实进展

截至 2026-05-16：

- Azure SQL `amazon_ops` 已完成初始建表与索引：`001_create_core_tables.sql` 29/29 batches，`002_create_indexes.sql` 54/54 batches。
- 当前真实数据库有 28 张用户表。
- Amazon Ads Sponsored Products 四类报表已完成真实入库：首次 inserted=200，重复执行 inserted=0、updated=200，幂等性验证通过。
- 已新增数据库检查脚本 `scripts/check_database_status.py`。
- SP-API Listing 快照入库已完成 dry-run、schema guard、repository/upsert、CLI、真实 Azure SQL execute 和幂等性验证：首次 inserted=6，重复执行 inserted=0、updated=6。
- Azure SQL 连接层已新增 retry + `SELECT 1` warm-up，用于处理 serverless 长时间 idle 后首次连接 timeout，自动化任务无需人工先手动唤醒数据库。

详细进展见：[`docs/project/progress_next_steps.md`](docs/project/progress_next_steps.md)。

## 文档入口

本项目从现在开始以 `docs/` 作为正式文档目录。`requirements/` 中的历史文档只作为迁移来源或兼容入口，不再作为新设计的主要维护位置。

| 文档 | 用途 |
|---|---|
| [`docs/README.md`](docs/README.md) | 文档体系总索引。 |
| [`docs/project/project_overview.md`](docs/project/project_overview.md) | 项目目的、边界、整体架构与当前阶段。 |
| [`docs/project/development_rules.md`](docs/project/development_rules.md) | 开发和文档维护规则，尤其面向 AI 迭代。 |
| [`docs/project/iteration_workflow.md`](docs/project/iteration_workflow.md) | 新需求到设计、migration、开发、验收和文档同步的端到端 SOP。 |
| [`docs/project/progress_next_steps.md`](docs/project/progress_next_steps.md) | 当前真实进度、已完成里程碑和下一步。 |
| [`docs/data_access/amazon_data_access_catalog.md`](docs/data_access/amazon_data_access_catalog.md) | Amazon 数据接入总目录，汇总 SP-API、Ads API、手动导出。 |
| [`docs/data_access/sp_api_reports_catalog.md`](docs/data_access/sp_api_reports_catalog.md) | SP-API Reports report type、获取方式、样例字段和状态。 |
| [`docs/data_access/amazon_ads_reports_catalog.md`](docs/data_access/amazon_ads_reports_catalog.md) | Amazon Ads API profile 和 Sponsored Products 报告接入目录。 |
| [`docs/features/README.md`](docs/features/README.md) | 功能设计文档索引。 |
| [`docs/features/FEATURE_TEMPLATE.md`](docs/features/FEATURE_TEMPLATE.md) | 单功能设计文档标准模板。 |
| [`docs/features/feature_azure_sql_foundation.md`](docs/features/feature_azure_sql_foundation.md) | Azure SQL 数据库基础设施功能文档。 |
| [`docs/features/feature_ads_ingestion.md`](docs/features/feature_ads_ingestion.md) | Amazon Ads Sponsored Products 报表入库功能文档。 |
| [`docs/features/feature_listing_snapshot_ingestion.md`](docs/features/feature_listing_snapshot_ingestion.md) | SP-API Listing 快照入库功能文档，已完成真实 execute 和幂等性验证。 |
| [`docs/database/database_current_schema_spec.md`](docs/database/database_current_schema_spec.md) | 当前真实 Azure SQL 表结构、字段、索引与数据来源。 |
| [`docs/database/database_migration_policy.md`](docs/database/database_migration_policy.md) | 数据库变更和 migration 规则。 |
| [`docs/adr/`](docs/adr/) | 架构决策记录。 |

## 目录结构

```text
SellerDataPipeline/
  README.md
  Dockerfile
  requirements.txt
  pyproject.toml
  .env.example

  docs/                         # 正式项目文档
    project/                    # 项目说明、开发规则、进度
    data_access/                # 数据接入目录：SP-API / Ads / 手动导出能拿到什么
    features/                   # 单功能设计文档
    database/                   # 当前 schema spec、migration policy、字段命名规范
    adr/                        # Architecture Decision Records

  sql/
    migrations/                 # Azure SQL migration；已执行过的 migration 不允许修改
    seeds/                      # 示例基础数据，例如 SKU 成本样例

  src/
    seller_data_pipeline/
      config/                   # 配置读取：环境变量、运行环境、默认参数
      common/                   # 公共工具：日志、日期窗口、金额处理、异常、重试
      integrations/amazon/      # Amazon SP-API / Ads API 客户端和下载逻辑
      parsers/amazon/           # Amazon 原始报告解析器
      ingestion/                # 字段映射、dry-run preview、schema guard、ingestion 编排
      db/                       # Azure SQL 连接、SQL 执行、Repository 层
      services/                 # 业务服务层
      reports/                  # 后续 Excel / 报表构建器
      jobs/                     # 后续 Azure Container Apps Job 入口

  scripts/                      # 命令行入口，原则上只做参数解析和调用业务层
  tests/                        # 单元测试和集成测试
  reports/raw/                  # 本地真实 raw report，已忽略，不提交
  runtime/                      # 本地运行 manifest / preview / temp output，已忽略，不提交
```

## 本地开发

建议使用 Python 3.11。

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` 不允许提交到 GitHub。真实密钥、refresh token、Azure SQL 密码、SMTP 密码等只能放本地 `.env` 或云端 Secret/Key Vault。

运行测试：

```bash
PYTHONPATH=src pytest -q
```

代码检查：

```bash
ruff check src tests scripts
ruff format src tests scripts
```

## 常用命令

Azure SQL 连接测试：

```bash
python scripts/test_azure_sql_connection.py --json
python scripts/test_azure_sql_connection.py --list-tables
python scripts/test_azure_sql_connection.py --json --max-attempts 5 --retry-delay-seconds 5
```

连接层默认会先 retry 已知 transient login timeout，并执行 `SELECT 1` warm-up，再把连接交给业务 SQL。

数据库状态检查：

```bash
python scripts/check_database_status.py
python scripts/check_database_status.py --json
python scripts/check_database_status.py --all-tables
```

执行新 SQL migration 时使用以下模式。注意当前 `001/002/003` 已经执行成功，后续新结构变化应从 `004_xxx.sql` 开始：

```bash
python scripts/run_sql_migration.py --file sql/migrations/004_xxx.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/004_xxx.sql
```

注意：`001_create_core_tables.sql`、`002_create_indexes.sql` 和 `003_add_listing_snapshot_business_key_hash.sql` 已经执行成功，后续不要修改这些历史 migration。任何结构变化都必须新增 `004_xxx.sql`、`005_xxx.sql`。当前 `docs/database/database_current_schema_spec.md` 已记录 003 带来的 Listing `business_key_hash` 字段和唯一过滤索引。

Amazon Ads 真实入库：

```bash
python scripts/ingest_ads_reports.py \
  --profile-id 3917953989967300 \
  --marketplace-id ATVPDKIKX0DER \
  --execute
```


SP-API Listing 快照 dry-run：

```bash
python scripts/ingest_listing_snapshot.py \
  --marketplace-id ATVPDKIKX0DER
```

SP-API Listing 快照真实入库，`003_add_listing_snapshot_business_key_hash.sql` 已执行成功，当前已完成验收；后续如需重跑可执行：

```bash
python scripts/ingest_listing_snapshot.py \
  --marketplace-id ATVPDKIKX0DER \
  --execute
```

重复执行同一命令应表现为 update，而不是重复 insert。

SP-API 连接测试：

```bash
python scripts/test_sp_api_connection.py
```

提交并下载 SP-API Reports：

```bash
PYTHONPATH=src python scripts/submit_report_requests.py \
  --report-type GET_MERCHANT_LISTINGS_ALL_DATA

PYTHONPATH=src python scripts/collect_ready_reports.py --limit 10
```

## 开发原则

1. 开发前先确认或更新对应文档，尤其是 `docs/features/feature_*.md`。
2. 新增数据源前先更新 `docs/data_access/` 下的数据接入目录。
3. 数据库变更前先对比 `docs/database/database_current_schema_spec.md`。
4. 已执行过的 migration 不允许修改，只能新增 migration。
5. migration 执行成功后必须更新当前 schema spec。
6. 入库逻辑必须支持 dry-run、schema guard、审计日志和幂等 upsert。
7. `reports/raw/`、`runtime/`、`.env` 中可能包含真实经营数据和密钥，禁止提交。

新需求到开发验收的完整 SOP 见：[`docs/project/iteration_workflow.md`](docs/project/iteration_workflow.md)。
更完整规则见：[`docs/project/development_rules.md`](docs/project/development_rules.md)。
