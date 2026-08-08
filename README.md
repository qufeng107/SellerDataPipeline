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

截至 2026-05-19：

- Azure SQL `amazon_ops` 已完成核心建表、索引和 001-012 migration，当前真实数据库有 29 张用户表。
- 核心 normalized ingestion 已完成真实 Azure SQL execute 和第二次 execute 幂等性验证：Ads、Listing、Inventory、Sales & Traffic、Settlement、Orders、FBA Reimbursements、FBA Fee Preview、Promotion/Coupon、Inventory Ledger。
- Azure SQL 连接层已支持 retry + `SELECT 1` warm-up，并能区分 idle/resume、firewall/IP allowlist 和登录错误。
- 已新增 `scripts/check_database_status.py` 与 `scripts/export_database_schema_spec.py`，用于检查运行状态和从 live schema 更新数据库 spec。
- 当前主线从“继续扩 ingestion”转为“手动运营流程 + 利润核算 + 周报/月报”。
- 已新增 manual-first operations 文档，并执行 `012_create_ingestion_job_config.sql` 与 `001_seed_ingestion_job_config_core_jobs.sql`，当前 `pipeline_job_config` 有 13 条任务配置；新增 seed 002 用于同步重叠窗口刷新策略。
- 利润核算口径已冻结为 Settlement-led Financial Profit v1.0：财务利润以 Settlement 为主，Orders / Ads / Promotion-Coupon 只做运营解释，SKU 成本来自 `amazon_sku_cost`。
- 已实现 SKU 成本 xlsx 模板导出/导入：先导出模板人工填写，再 dry-run/execute 写入 `amazon_sku_cost`。
- 已冻结数据刷新策略：核心源可每 1-2 天重叠窗口刷新并 upsert，销售/广告/利润等正式分析产物最短周期为一周。

详细进展见：[`docs/project/progress_next_steps.md`](docs/project/progress_next_steps.md)。

## 文档入口

本项目从现在开始以 `docs/` 作为正式文档目录。`requirements_to_be_deprecated/` 中的历史文档只作为迁移来源或兼容参考，不再作为新设计的主要维护位置；暂不建议直接删除，详见 `docs/project/requirements_deprecation_plan.md`。

| 文档 | 用途 |
|---|---|
| [`docs/README.md`](docs/README.md) | 文档体系总索引。 |
| [`docs/project/project_overview.md`](docs/project/project_overview.md) | 项目目的、边界、整体架构与当前阶段。 |
| [`docs/project/development_rules.md`](docs/project/development_rules.md) | 开发和文档维护规则，尤其面向 AI 迭代。 |
| [`docs/project/iteration_workflow.md`](docs/project/iteration_workflow.md) | 新需求到设计、migration、开发、验收和文档同步的端到端 SOP。 |
| [`docs/project/progress_next_steps.md`](docs/project/progress_next_steps.md) | 当前真实进度、已完成里程碑和下一步。 |
| [`docs/operations/README.md`](docs/operations/README.md) | 手动执行流程、数据更新周期和未来自动化运行手册入口。 |
| [`docs/operations/manual_execution_workflow.md`](docs/operations/manual_execution_workflow.md) | 手动下载、入库、加工、复核和邮件发送流程。 |
| [`docs/operations/data_refresh_policy.md`](docs/operations/data_refresh_policy.md) | 数据源重叠窗口刷新、stable cutoff 和周度分析产物规则。 |
| [`docs/operations/ingestion_job_cadence_catalog.md`](docs/operations/ingestion_job_cadence_catalog.md) | 每类数据源的建议下载/入库周期，未来自动化 Jobs 的调度依据。 |
| [`docs/operations/data_coverage_audit_workflow.md`](docs/operations/data_coverage_audit_workflow.md) | 利润/周报前检查 normalized 数据覆盖范围和 stable cutoff。 |
| [`docs/operations/manual_refresh_plan_workflow.md`](docs/operations/manual_refresh_plan_workflow.md) | 标准定期刷新入口，用少数固定命令完成 submit / collect / ingest / audit。 |
| [`docs/project/core_ingestion_completion_review.md`](docs/project/core_ingestion_completion_review.md) | 核心入库阶段收尾检查。 |
| [`docs/project/requirements_deprecation_plan.md`](docs/project/requirements_deprecation_plan.md) | 旧 requirements 目录保留/删除规则。 |
| [`docs/data_access/amazon_data_access_catalog.md`](docs/data_access/amazon_data_access_catalog.md) | Amazon 数据接入总目录，汇总 SP-API、Ads API、手动导出。 |
| [`docs/data_access/sp_api_reports_catalog.md`](docs/data_access/sp_api_reports_catalog.md) | SP-API Reports report type、获取方式、样例字段和状态。 |
| [`docs/data_access/amazon_ads_reports_catalog.md`](docs/data_access/amazon_ads_reports_catalog.md) | Amazon Ads API profile 和 Sponsored Products 报告接入目录。 |
| [`docs/features/README.md`](docs/features/README.md) | 功能设计文档索引。 |
| [`docs/features/FEATURE_TEMPLATE.md`](docs/features/FEATURE_TEMPLATE.md) | 单功能设计文档标准模板。 |
| [`docs/features/feature_azure_sql_foundation.md`](docs/features/feature_azure_sql_foundation.md) | Azure SQL 数据库基础设施功能文档。 |
| [`docs/features/feature_ads_ingestion.md`](docs/features/feature_ads_ingestion.md) | Amazon Ads Sponsored Products 报表入库功能文档。 |
| [`docs/features/feature_listing_snapshot_ingestion.md`](docs/features/feature_listing_snapshot_ingestion.md) | SP-API Listing 快照入库功能文档，已完成真实 execute 和幂等性验证。 |
| [`docs/features/feature_inventory_ingestion.md`](docs/features/feature_inventory_ingestion.md) | SP-API FBA Inventory 快照入库功能文档，已完成真实 execute 和幂等性验证。 |
| [`docs/features/feature_sales_traffic_ingestion.md`](docs/features/feature_sales_traffic_ingestion.md) | SP-API Sales & Traffic 入库功能文档；`005` migration、dry-run、真实 execute 和幂等性验证已完成。 |
| [`docs/features/feature_settlement_ingestion.md`](docs/features/feature_settlement_ingestion.md) | SP-API Settlement 入库功能文档；`006` migration、dry-run、真实 execute 和幂等性验证已完成。 |
| [`docs/features/feature_orders_ingestion.md`](docs/features/feature_orders_ingestion.md) | SP-API Orders 入库功能文档；007、dry-run、真实 execute 和幂等性验证已完成。 |
| [`docs/features/feature_fba_reimbursements_ingestion.md`](docs/features/feature_fba_reimbursements_ingestion.md) | SP-API FBA Reimbursements 入库功能文档；`008` 已执行，dry-run、execute 和幂等性验证已完成。 |
| [`docs/features/feature_fba_fee_preview_ingestion.md`](docs/features/feature_fba_fee_preview_ingestion.md) | SP-API FBA Fee Preview 入库功能文档；009、dry-run、execute 与幂等验证已完成。 |
| [`docs/features/feature_promotion_coupon_ingestion.md`](docs/features/feature_promotion_coupon_ingestion.md) | Promotion/Coupon 入库功能文档；010、dry-run、execute 与幂等验证已完成。 |
| [`docs/features/feature_inventory_ledger_ingestion.md`](docs/features/feature_inventory_ledger_ingestion.md) | Inventory Ledger 入库功能文档；011 已执行，专用 dry-run 已完成，已完成 execute/幂等验证。 |
| [`docs/features/feature_ingestion_job_config.md`](docs/features/feature_ingestion_job_config.md) | 数据下载/入库/加工/报表任务周期配置表设计；012 migration 和 seed 001 已执行，seed 002 用于更新刷新策略。 |
| [`docs/features/feature_profit_calculation.md`](docs/features/feature_profit_calculation.md) | 利润核算功能设计；口径已冻结为 Settlement-led Financial Profit v1.0，第一版利润 preview 已实现。 |
| [`docs/features/feature_sku_cost_management.md`](docs/features/feature_sku_cost_management.md) | SKU 成本 xlsx 模板导出/导入功能；用于维护 `amazon_sku_cost`。 |
| [`docs/features/feature_monthly_financial_close_report.md`](docs/features/feature_monthly_financial_close_report.md) | 月度财务结算报表设计；CEO/CFO 财务结算和 SKU 利润分析。 |
| [`docs/features/feature_weekly_business_review.md`](docs/features/feature_weekly_business_review.md) | 每周经营周报设计；销售、流量、广告、SKU、库存和风险行动建议。 |
| [`docs/features/feature_weekly_ads_optimization_report.md`](docs/features/feature_weekly_ads_optimization_report.md) | 每周广告优化报表设计；输出 campaign/keyword/search term/SKU 广告动作清单。 |
| [`docs/database/database_current_schema_spec.md`](docs/database/database_current_schema_spec.md) | 当前真实 Azure SQL 表结构、字段、索引与数据来源。 |
| [`docs/database/database_migration_policy.md`](docs/database/database_migration_policy.md) | 数据库变更和 migration 规则。 |
| [`docs/database/database_schema_export_tool.md`](docs/database/database_schema_export_tool.md) | 从真实 Azure SQL 导出 schema snapshot 的工具说明。 |
| [`docs/database/azure_sql_connection_runbook.md`](docs/database/azure_sql_connection_runbook.md) | Azure SQL idle/resume、firewall/IP、账号密码等连接问题排查。 |
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
    operations/                 # 手动运行流程、任务周期、未来自动化 runbook
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
# CI blocking：只检查高信号的正确性/潜在 bug 规则（由 pyproject.toml 配置）
ruff check src tests

# 本地维护：格式和 import/pyupgrade 可自动修复，不作为 CI 阻断条件
ruff check src tests scripts --select I,UP --fix
ruff format src tests scripts
```

## 常用命令

标准定期更新入口：

```bash
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase collect --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase audit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --target-start-date 2026-03-01 --execute
```


Azure SQL 连接测试：

```bash
python scripts/test_azure_sql_connection.py --json
python scripts/test_azure_sql_connection.py --list-tables
python scripts/test_azure_sql_connection.py --json --max-attempts 8 --retry-delay-seconds 8
```

连接层默认会先 retry 已知 transient login timeout，并执行 `SELECT 1` warm-up，再把连接交给业务 SQL。

数据库状态检查：

```bash
python scripts/check_database_status.py
python scripts/check_database_status.py --json
python scripts/check_database_status.py --all-tables
```

真实 schema 导出，用于 migration 后更新 current spec：

```bash
python scripts/export_database_schema_spec.py
python scripts/export_database_schema_spec.py --output-prefix after_013_xxx --include-row-counts
python scripts/export_database_schema_spec.py --stdout-markdown
```

执行新 SQL migration 时使用以下模式。当前 `001/002/003/004/005/006/007/008/009/010/011/012` 已经执行成功并锁定；后续结构变化必须从 `013_xxx.sql` 开始。

```bash
python scripts/run_sql_migration.py --file sql/migrations/013_xxx.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/013_xxx.sql
```

注意：已执行过的 migration 不允许修改。后续任何结构变化都必须新增 migration。migration 执行成功并导出 live schema 后，才可把新字段或新索引写入 current schema spec。

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

利润核算口径已冻结，第一版 preview 已实现；入口如下：

```bash
python scripts/calculate_profit_report.py --marketplace-id ATVPDKIKX0DER --period weekly --start-date YYYY-MM-DD --end-date YYYY-MM-DD --dry-run
```

第一版利润 preview 不应自动发送邮件，必须人工复核 Settlement、SKU 成本、广告、促销和异常项后再使用。

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


SP-API Inventory 快照真实入库，`004_add_inventory_daily_business_key_hash.sql` 已执行成功且当前已完成验收；后续如需重跑可执行：

```bash
python scripts/ingest_inventory_snapshot.py \
  --marketplace-id ATVPDKIKX0DER \
  --execute
```

当前计划链路已经切换为 利润核算设计。FBA Fee Preview 与 Promotion/Coupon 均已完成真实 execute 和幂等性验证；下一步为 利润核算设计，为后续周报库存 movement 和库存审计提供数据口径：

```text
GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA
  -> feature_fba_fee_preview_ingestion.md
  -> amazon_fba_fee_preview 已建表
  -> 009_add_fba_fee_preview_business_key.sql 已执行，live schema 已导出
  -> 专用 dry-run/schema guard/repository/CLI 已开发并通过 dry-run
```



## Promotion/Coupon 与 Inventory Ledger 补充数据

2026-05-17 已新增两份功能设计并准备对应 migration：

```text
docs/features/feature_promotion_coupon_ingestion.md
sql/migrations/010_add_promotion_coupon_business_keys.sql

docs/features/feature_inventory_ledger_ingestion.md
sql/migrations/011_add_inventory_ledger_business_keys.sql
```

Promotion/Coupon 用于优惠券、折扣、会员日/Prime Day 等活动效果分析，已完成入库验收；Inventory Ledger 用于库存 movement 与库存审计，已完成 execute/幂等验证。周报中的当前库存余额仍优先来自 `amazon_inventory_daily`，Ledger 用于解释库存变化。
