# SellerDataPipeline 开发与文档维护规则

> 更新时间：2026-08-08  
> 文档定位：定义本项目后续开发、文档、数据库、测试和 AI 迭代的硬规则。任何新功能、新表结构、新数据源或重构，都应先阅读本文件。

## 1. 总原则

本项目后续会大量依赖 AI 辅助开发。为了避免需求、设计、代码、数据库真实状态逐渐偏移，所有迭代必须遵守以下原则：

1. **事实和计划分离**：已经真实执行的内容写入 progress 和 current schema spec；未来设计写入 feature 文档或 data access 文档。
2. **数据接入和业务功能分离**：数据接入文档只写能从 Amazon 拿到什么；功能文档才写如何使用这些数据。
3. **功能设计和当前数据库 spec 分离**：功能文档可以写目标设计；current schema spec 只记录真实 Azure SQL 当前状态。
4. **先文档后实现**：新增功能前必须先确认或更新对应功能文档。
5. **先 migration 后 spec**：数据库真实结构变化必须通过 migration 执行；执行成功后再更新 current schema spec。
6. **不修改已执行 migration**：已在 Azure SQL 执行成功的 migration 是历史事实，禁止回改。
7. **所有 ingestion 必须可审计**：必须有 dry-run、schema guard、run log、validation event 和幂等性验证。
8. **Schema guard 保护数据契约而不是完整字段一致性**：新增 unknown field 默认只告警、不阻断；只有 required field 缺失、关键语义变化、关键解析失败等才阻断。详见 ADR-013。
9. **真实 SQL 前必须连接预热**：migration、ingestion、检查脚本等真实数据库入口必须使用 `get_connection()`，不得直接绕开 Azure SQL retry + `SELECT 1` warm-up。

## 2. 文档维护规则

### 2.1 README

根目录 `README.md` 是项目总入口，负责：

- 说明项目目的和当前阶段。
- 指向 `docs/` 下的正式文档。
- 给出最常用的本地开发命令。
- 不承载过长字段映射、完整表结构或长篇设计细节。

### 2.2 docs/project

`docs/project/` 负责项目级信息：

- `project_overview.md`：项目目的、边界、架构、当前状态。
- `development_rules.md`：开发规则和文档维护规则。
- `iteration_workflow.md`：新需求到设计、migration、开发、验收和文档同步的端到端 SOP。
- `progress_next_steps.md`：真实进展、当前阻塞、下一步计划。

### 2.3 docs/data_access

`docs/data_access/` 后续用于记录数据接入目录。它只回答：

```text
我们能从 Amazon / Ads / Seller Central 拿到什么数据？
```

它不应写：

- 利润公式。
- 周报口径。
- 广告优化策略。
- 具体业务功能输出。

### 2.4 docs/features

`docs/features/` 每个功能一份文档，必须按照 `FEATURE_TEMPLATE.md` 编写。功能文档回答：

```text
这个功能解决什么问题？输入哪些数据？怎么处理？写哪些表？如何验收？
```

功能文档必须明确状态：

```text
Proposed / Planned / Implementing / Implemented / Deprecated
```

### 2.5 docs/database

`docs/database/` 负责数据库事实和数据库治理：

- `database_current_schema_spec.md`：当前真实 Azure SQL 表结构、字段、索引、数据来源。
- `database_migration_policy.md`：migration 和 schema spec 维护规则。

注意：`database_current_schema_spec.md` 不是未来设计文档，不允许把未执行的目标表结构写成事实。

### 2.6 docs/adr

ADR 用于记录长期架构决策。适合写入 ADR 的内容包括：

- 为什么使用 Azure SQL。
- 为什么 raw file first。
- 为什么已执行 migration 不允许修改。
- 为什么 schema guard 必须在入库前执行。
- 为什么 feature doc 必须先于 migration。

ADR 不用于记录短期 TODO。

## 3. 开发流程规则

### 3.0 标准迭代入口

任何新需求、新功能、数据库变更或重构，先阅读并执行：

```text
docs/project/iteration_workflow.md
```

该 SOP 定义：

1. 如何识别需求类型。
2. 先读哪些文档。
3. 何时更新 data access / feature 文档。
4. 何时新增 migration。
5. migration 执行后如何查询真实 Azure SQL schema。
6. 如何更新 `database_current_schema_spec.md`。
7. 如何验收 dry-run、execute、幂等性和文档同步。

### 3.1 新增数据源

新增 Amazon report、Ads report 或 Seller Central 手动导出前：

1. 更新 `docs/data_access/` 对应 catalog。
2. 记录 report type、接口、请求参数、文件格式、字段结构、取样路径。
3. 明确当前状态：未下载 / 已下载 / 已解析 / 已入库。
4. 再开发 downloader / parser / analyzer。
5. 生成或更新脱敏样例文档。

### 3.2 新增功能

新增功能前：

1. 复制 `docs/features/FEATURE_TEMPLATE.md`。
2. 创建 `docs/features/feature_xxx.md`。
3. 写清业务目标、输入数据、处理流程、目标表、字段映射、幂等性、异常审计和验收标准。
4. 如果涉及数据库变化，先在功能文档中说明设计，再对比 current schema spec。
5. 代码实现完成后更新功能文档状态和 progress。

### 3.3 修改数据库结构

任何数据库结构变化必须遵守：

1. 不修改已执行过的 migration。
2. 新增 `sql/migrations/NNN_short_description.sql`。
3. migration 必须可重复检查，优先使用 `IF OBJECT_ID(...) IS NULL`、`IF COL_LENGTH(...) IS NULL`、`IF NOT EXISTS(...)`。
4. 先 dry-run 或人工检查 SQL；dry-run 不连接数据库，只验证 SQL batch 拆分。
5. 执行真实 SQL 前，确认入口使用项目连接层 `get_connection()`；该连接层会处理 Azure SQL serverless idle/resume 的首次连接 timeout，并执行 `SELECT 1` warm-up。
6. 执行成功后，必须按照 `docs/project/iteration_workflow.md` 查询真实 Azure SQL 字段、索引、约束。
7. 优先运行 `scripts/export_database_schema_spec.py` 导出 live schema snapshot；必要时再用手工 SQL 精查。
8. 根据真实查询/导出结果更新 `docs/database/database_current_schema_spec.md`。
9. 同步更新相关 feature 文档和 progress。

### 3.4 修改 ingestion 链路

所有 ingestion 链路应遵守 Ads / Listing 已验证的模式：

```text
raw file
  -> parser
  -> schema guard
  -> dry-run preview
  -> repository upsert
  -> Azure SQL
  -> sync_run_log / schema_validation_event
```

最低要求：

- 支持 dry-run，不写数据库也能生成 preview。
- 支持 execute 模式，真实写库前必须经过 schema guard。
- schema guard 默认采用向后兼容数据契约：`expected_fields` 与 `required_fields` 分离；additive new fields 记录 warning/event 但不阻断，missing required / semantic incompatibility / critical parse failure 才阻断。
- 写库必须幂等，重复执行同一批数据不能重复插入。
- 写库入口必须使用 `get_connection()`，让数据库连接先完成 retry + `SELECT 1` warm-up。
- 写入后必须能通过检查脚本或 SQL 查询验证行数和 run log。
- 新增 repository 必须有单元测试。


### 3.5 Azure SQL 连接预热规则

Azure SQL serverless 长时间空闲后可能自动暂停。恢复期间第一次连接可能失败，但第二次或稍后再连会成功。项目统一在 `src/seller_data_pipeline/db/connection.py` 处理：

```text
pyodbc.connect retry for retryable connection errors
  -> SELECT 1 warm-up
  -> yield verified connection to business SQL
```

规则：

1. 不要在脚本或 repository 中直接调用 `pyodbc.connect()`。
2. 不要在业务层自行写重复的连接重试逻辑。
3. 连接层只重试连接和 warm-up，不重试业务 SQL。
4. Azure SQL firewall/IP allowlist 错误不是 warm-up 问题，不能通过增加 retry 解决；应先在 Azure SQL Server firewall 放行当前公网 IP，或为云端任务配置稳定出站网络。
5. 自动化任务可通过环境变量调整重试次数和等待时间：`AZURE_SQL_CONNECT_MAX_ATTEMPTS`、`AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS`、`AZURE_SQL_CONNECT_RETRY_BACKOFF`。
6. 连接问题排查见 `docs/database/azure_sql_connection_runbook.md`。

## 4. 代码结构规则

1. `scripts/` 只做参数解析和调用，不写复杂业务逻辑。
2. API 客户端放在 `src/seller_data_pipeline/integrations/amazon/`。
3. 原始文件解析放在 `src/seller_data_pipeline/parsers/amazon/`。
4. 入库编排、字段映射、schema guard 放在 `src/seller_data_pipeline/ingestion/`。
5. 数据库写入放在 `src/seller_data_pipeline/db/repositories/`。
6. 公共工具放在 `src/seller_data_pipeline/common/`。
7. 单元测试按源码模块镜像组织。

## 5. 测试和验证规则

每次代码变更后至少运行：

```bash
PYTHONPATH=src pytest -q
python -m compileall -q scripts src tests
```

如果环境安装了 Ruff：

```bash
ruff check src tests scripts
ruff format src tests scripts
```

涉及数据库的变更还应运行：

```bash
python scripts/test_azure_sql_connection.py --json
python scripts/check_database_status.py
```

涉及 ingestion 的变更应至少验证：

1. dry-run 成功。
2. execute 成功。
3. 重复 execute 幂等性通过。
4. 目标表行数符合预期。
5. `amazon_sync_run_log` 有记录。
6. `amazon_schema_validation_event` 无 blocking error。

## 6. 安全规则

禁止提交：

- `.env`
- Amazon LWA Client ID / Client Secret
- SP-API refresh token
- Amazon Ads refresh token
- Azure SQL 密码
- SMTP 密码
- Azure Storage connection string
- 真实 raw report 文件
- 未脱敏的 SKU、ASIN、订单、客户相关数据样例

允许提交：

- 脱敏后的字段结构样例。
- 不含真实密钥的 `.env.example`。
- 不含敏感值的测试 fixture。

## 7. AI 迭代提示规则

当把任务交给 AI 时，应尽量明确：

1. 本次只修改哪些文档或哪些功能。
2. 是否允许修改代码。
3. 是否允许新增 migration。
4. 是否禁止修改已执行 migration。
5. 哪个 feature 文档是本次需求来源。
6. 需要运行哪些测试。
7. 输出应采用 updated files only overlay package，而不是整包项目。

建议固定指令：

```text
请先阅读 README.md、docs/README.md、docs/project/iteration_workflow.md、docs/project/development_rules.md、docs/project/progress_next_steps.md、相关 feature 文档和 database_current_schema_spec.md。
不得修改已执行的 migration。
如需数据库变更，先说明与 current schema spec 的差异，再新增 migration。
完成后按 iteration_workflow.md 验收，并更新 progress_next_steps.md。
```

## 10. Manual-first 与任务周期规则

当前阶段采用 manual-first 策略。任何自动化 Jobs 开发前，必须先保证对应能力能手动执行：

```text
手动下载 raw data
-> 手动入库
-> 手动加工报表
-> 人工复核
-> 手动或半自动发送邮件
```

新增或调整数据下载/入库周期时，必须同步更新：

```text
docs/operations/ingestion_job_cadence_catalog.md
docs/features/feature_ingestion_job_config.md
```

如果该周期需要程序读取，必须写入或更新：

```text
pipeline_job_config
```

`pipeline_job_config` 记录计划和配置；`amazon_sync_run_log` 记录实际运行结果。两者不可混用。

## 11. 历史 requirements 目录规则

`requirements_to_be_deprecated/` 当前只作为历史迁移来源。新需求、新设计、新数据库 spec、新进度记录必须写入 `docs/`。

删除旧目录前必须按以下计划执行：

```text
docs/project/requirements_deprecation_plan.md
```
