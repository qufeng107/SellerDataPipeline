# SellerDataPipeline 迭代工作流 SOP

> 更新时间：2026-05-16  
> 文档定位：本文件是后续 AI / 开发者迭代 SellerDataPipeline 的端到端操作流程。它把“新需求提出后先做什么、何时写文档、何时改代码、何时改数据库、如何验收、如何更新真实 schema spec”固定下来。  
> 相关文档：`docs/project/development_rules.md`、`docs/database/database_migration_policy.md`、`docs/features/FEATURE_TEMPLATE.md`、`docs/database/database_current_schema_spec.md`。

## 1. 为什么需要这份 SOP

SellerDataPipeline 已经从探索阶段进入真实数据库落地阶段。当前已经完成：

```text
SP-API / Ads API 取样
-> docs/ 文档体系建立
-> Azure SQL 001/002 建表和索引
-> Amazon Ads 四张 normalized 表真实入库
-> Ads 重复 execute 幂等性验证
-> Listing 003 migration 执行并同步 current schema spec
```

后续项目会继续由 AI 辅助开发。为了避免“需求、设计、代码、SQL、真实数据库、文档”逐渐偏移，所有迭代必须按本 SOP 执行。

本 SOP 的核心目标：

1. 每个新需求都有明确入口文档。
2. 每个功能先有设计，再写代码。
3. 数据库结构变化先有差异说明，再新增 migration。
4. migration 执行后，从真实 Azure SQL 读取 schema，再更新 current schema spec。
5. 每次开发都能用固定验收标准判断是否完成。
6. 后续 AI 可以根据文档恢复上下文，而不是依赖聊天记录。

## 2. 文档和事实来源优先级

遇到信息冲突时，按以下优先级判断：

| 优先级 | 来源 | 说明 |
|---:|---|---|
| 1 | 真实 Azure SQL `amazon_ops` | 数据库当前实际状态，尤其是表、字段、索引、已写入数据。 |
| 2 | `docs/database/database_current_schema_spec.md` | 已同步过的真实数据库结构记录。若怀疑滞后，必须重新查询真实 Azure SQL。 |
| 3 | 已执行 migration 文件和 progress 记录 | 数据库演进历史，已执行 migration 不可回改。 |
| 4 | `docs/features/feature_*.md` | 功能设计、字段映射、实现状态和验收标准。 |
| 5 | `docs/data_access/*.md` | 能从 Amazon / Ads / Seller Central 拿到的数据目录。 |
| 6 | `requirements/` 历史文档 | 只作为迁移来源或旧背景参考，不再作为新设计的唯一事实。 |
| 7 | 聊天记录 | 仅作补充背景；重要结论必须沉淀到 `docs/`。 |

## 3. 一次标准迭代的总流程

任何新需求都先走这个总流程：

```text
1. 识别需求类型
2. 读取相关文档和当前真实状态
3. 更新或创建设计文档
4. 判断是否需要数据库变更
5. 如需数据库变更：新增 migration -> dry-run -> 连接 warm-up -> 执行 -> 查询真实 schema -> 更新 current schema spec
6. 写代码实现
7. 运行测试和业务验收
8. 更新功能文档状态、progress、必要的 README / docs index
9. 输出 updated files only overlay package
```

除紧急修复外，不允许跳过“先确认设计文档”这一步。紧急修复完成后也必须补齐文档。

## 4. 第一步：识别需求类型

接到新需求后，先归类。一个需求可能同时属于多类，但必须明确主类型。

| 需求类型 | 示例 | 先更新/读取的文档 |
|---|---|---|
| 新数据源接入 | 新增一个 SP-API report、Ads report、Seller Central 手动导出 | `docs/data_access/*.md` |
| 新 normalized 入库功能 | Listing、库存、销售流量、结算入库 | `docs/features/feature_*.md` |
| 新业务分析功能 | 利润核算、周报、清仓决策、广告优化建议 | `docs/features/feature_*.md` |
| 数据库结构变更 | 新增字段、索引、表、约束 | `docs/database/database_current_schema_spec.md` + 相关 feature 文档 |
| 修复 bug | parser 错误、upsert 错误、schema guard 误判 | 相关 feature 文档 + 测试 |
| 重构 | 抽象公共 ingestion 框架、整理 repository | 相关 feature 文档 + `development_rules.md` |
| 文档治理 | 新增 ADR、调整文档结构、迁移历史文档 | `docs/README.md` + `docs/adr/*.md` |
| 部署/自动化 | Azure Container Apps Jobs、Key Vault、定时任务 | 新建对应 feature 文档和 ADR（如有长期架构决策） |

如果需求类型不清楚，应先在回复中说明判断和建议，不要直接改代码。

## 5. 第二步：读取上下文

开始任何迭代前，至少阅读：

```text
README.md
docs/README.md
docs/project/project_overview.md
docs/project/development_rules.md
docs/project/progress_next_steps.md
```

如果涉及数据源，继续阅读：

```text
docs/data_access/amazon_data_access_catalog.md
对应的 sp_api_reports_catalog.md / amazon_ads_reports_catalog.md / seller_central_manual_exports.md
```

如果涉及某个功能，继续阅读：

```text
docs/features/FEATURE_TEMPLATE.md
对应的 docs/features/feature_xxx.md
```

如果涉及数据库，继续阅读：

```text
docs/database/database_migration_policy.md
docs/database/database_current_schema_spec.md
已执行 migration 文件：sql/migrations/001... 002... 003...
```

AI 接手时，不应只根据最新用户消息直接改代码。

## 6. 第三步：先写或更新设计文档

### 6.1 新数据源

新增数据源前，先更新 `docs/data_access/`。数据接入文档只回答：

```text
能拿到什么？从哪里拿？格式是什么？字段有哪些？当前状态是什么？
```

必须记录：

| 项目 | 说明 |
|---|---|
| source_system | `sp_api` / `amazon_ads` / `seller_central_manual_export` |
| report/API 名称 | 例如 `GET_MERCHANT_LISTINGS_ALL_DATA` / `spCampaigns` |
| 获取方式 | API endpoint、report type、reportOptions、手动路径等 |
| 文件格式 | JSON、TSV、CSV、TXT、Excel 等 |
| 样例路径 | 本地 raw 路径或脱敏样例文档路径 |
| 源字段 | 观察到的字段列表和字段数量 |
| 当前状态 | 未下载 / 已下载 / 已解析 / 已入库 / 弃置 |
| 敏感信息 | 是否含订单、客户、地址、金额、广告数据等 |

不得在数据接入文档里写利润计算、周报逻辑、清仓策略等业务功能。

### 6.2 新功能

新增功能前，复制 `docs/features/FEATURE_TEMPLATE.md`，创建：

```text
docs/features/feature_xxx.md
```

功能文档必须先写清：

1. 功能状态：`Proposed / Planned / Implementing / Implemented / Deprecated`。
2. 业务目标：解决什么运营问题。
3. 输入数据：引用哪些 data_access 条目。
4. 输出结果：写库、报表、文件、告警、分析结论等。
5. 处理流程：下载、解析、schema guard、dry-run、upsert、聚合、输出。
6. 字段映射：源字段 -> 标准字段 -> 数据库字段。
7. 数据库设计：目标表、业务键、索引、来源追溯字段。
8. 幂等性规则：重复执行如何处理。
9. 异常与审计：何时 `requires_review=True`，何时阻塞入库。
10. 验收标准：命令、预期行数、run log、validation event、重复执行结果。
11. 相关代码路径：script、parser、ingestion、repository、tests。
12. 当前实现程度：已完成、待开发、后续优化、弃置项。

设计未明确前，不进入代码实现。

## 7. 第四步：判断是否需要数据库变更

每次功能设计完成后，要明确回答：

```text
当前真实数据库是否已经支持这个功能？
```

判断方式：

1. 阅读 `docs/database/database_current_schema_spec.md`。
2. 对比功能文档中的目标表、字段、索引、唯一键。
3. 如有疑问，直接查询 Azure SQL 真实结构。
4. 将差异写入功能文档的 “Migration 需求” 部分。

差异类型包括：

| 差异类型 | 处理方式 |
|---|---|
| 目标表不存在 | 新增 migration 创建表。 |
| 字段不存在 | 新增 migration 添加字段。 |
| 字段类型不合适 | 新增 migration 修改字段或新增替代字段；必须考虑历史数据。 |
| 唯一键/索引不存在 | 新增 migration 添加索引。 |
| 审计字段缺失 | 评估是否本期新增或记录为后续优化。 |
| 不需要结构变化 | 在功能文档中明确“current schema already supports this feature”。 |

## 8. 数据库变更标准流程

数据库变更必须按以下顺序。注意：Azure SQL serverless 长时间 idle 后可能在恢复期间出现首次连接超时；所有真实 SQL 执行都必须通过项目连接层 `get_connection()`，先完成 retry 和 `SELECT 1` warm-up 后再执行业务 SQL。

```text
1. 在 feature 文档中说明业务原因和目标结构
2. 对比 current schema spec，列出差异
3. 新增 sql/migrations/NNN_xxx.sql
4. dry-run migration；只检查 SQL batch 拆分，不连接数据库
5. 连接 warm-up / 状态确认；手动可跑 test_azure_sql_connection，自动化依赖 get_connection 内置 retry
6. 正式执行 migration
7. 优先运行 `scripts/export_database_schema_spec.py` 导出真实 Azure SQL schema；必要时再用手工 SQL 精查字段/索引/约束
8. 根据导出结果和人工确认更新 docs/database/database_current_schema_spec.md
9. 更新相关 feature 文档 migration 状态
10. 更新 docs/project/progress_next_steps.md
11. 必要时更新 README.md 和 docs/README.md
```

### 8.1 禁止事项

1. 禁止修改已执行 migration。
2. 禁止把未执行的目标结构写入 current schema spec。
3. 禁止只根据 SQL 文件推断真实结构，必须在执行后查询真实数据库。
4. 禁止在 migration 中写入真实密钥或经营数据。
5. 禁止绕过 repository 层直接在业务代码里散落 SQL 写入逻辑。

### 8.2 当前已执行且锁定的 migration

截至 2026-05-16，以下 migration 已执行并锁定：

```text
001_create_core_tables.sql -> 29/29 batches
002_create_indexes.sql -> 54/54 batches
003_add_listing_snapshot_business_key_hash.sql -> 3/3 batches
```

下一次结构变更从：

```text
004_xxx.sql
```

开始。

## 9. 如何读取完整真实数据库结构

`database_current_schema_spec.md` 必须来自真实 Azure SQL，而不是只看 SQL 文件。

### 9.1 连接和表数量检查

```bash
python scripts/test_azure_sql_connection.py --json
python scripts/test_azure_sql_connection.py --json --max-attempts 8 --retry-delay-seconds 8
python scripts/test_azure_sql_connection.py --list-tables
python scripts/check_database_status.py --all-tables
```

这些命令用于快速确认连接、表数量和重点表行数，但不足以完整导出字段和索引。`test_azure_sql_connection.py` 和所有使用 `get_connection()` 的真实 SQL 入口都会先执行连接 retry + `SELECT 1` warm-up。

### 9.2 推荐方式：导出真实 schema snapshot

日常更新 `database_current_schema_spec.md` 时，优先使用项目脚本导出完整 live schema：

```bash
python scripts/export_database_schema_spec.py
python scripts/export_database_schema_spec.py --output-prefix after_004_xxx --include-row-counts
python scripts/export_database_schema_spec.py --stdout-markdown
```

该脚本会读取：

```text
sys.tables / sys.columns / sys.types / sys.default_constraints
sys.indexes / sys.index_columns
sys.key_constraints
sys.foreign_keys / sys.foreign_key_columns
可选 sys.dm_db_partition_stats 行数
```

默认输出到：

```text
runtime/schema_exports/
```

导出文件用途：

1. 确认 migration 目标字段、索引、约束真实存在。
2. 对比 `docs/database/database_current_schema_spec.md` 是否滞后。
3. 辅助 AI 或开发者更新正式 current spec。

注意：导出的 Markdown/JSON 是 live schema snapshot，不是正式 spec。正式 spec 仍然是 `docs/database/database_current_schema_spec.md`，因为它还需要包含人工字段说明、数据来源、真实入库状态和限制说明。

详细说明见：

```text
docs/database/database_schema_export_tool.md
```

### 9.3 手工方式：完整字段结构 SQL

在 Azure Portal Query editor、Azure Data Studio、SSMS 或其他 SQL 客户端执行：

```sql
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    c.column_id,
    c.name AS column_name,
    ty.name AS data_type,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    dc.definition AS default_definition
FROM sys.tables t
JOIN sys.schemas s
    ON t.schema_id = s.schema_id
JOIN sys.columns c
    ON t.object_id = c.object_id
JOIN sys.types ty
    ON c.user_type_id = ty.user_type_id
LEFT JOIN sys.default_constraints dc
    ON c.default_object_id = dc.object_id
WHERE s.name = 'dbo'
ORDER BY t.name, c.column_id;
```

更新 spec 时要把 SQL Server 类型转换成人可读格式，例如：

```text
NVARCHAR(100)
DECIMAL(18, 4)
DATETIME2(7)
BIGINT IDENTITY
```

注意 `max_length` 对 `NVARCHAR` 是字节数，`NVARCHAR(100)` 在 `sys.columns.max_length` 中通常显示为 `200`。

### 9.4 手工方式：完整索引结构 SQL

```sql
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    i.name AS index_name,
    i.is_unique,
    i.has_filter,
    i.filter_definition,
    STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS key_columns,
    STRING_AGG(CASE WHEN ic.is_included_column = 1 THEN c.name END, ', ') AS included_columns
FROM sys.indexes i
JOIN sys.tables t
    ON i.object_id = t.object_id
JOIN sys.schemas s
    ON t.schema_id = s.schema_id
JOIN sys.index_columns ic
    ON i.object_id = ic.object_id
   AND i.index_id = ic.index_id
JOIN sys.columns c
    ON ic.object_id = c.object_id
   AND ic.column_id = c.column_id
WHERE s.name = 'dbo'
  AND i.name IS NOT NULL
GROUP BY
    s.name,
    t.name,
    i.name,
    i.is_unique,
    i.has_filter,
    i.filter_definition
ORDER BY t.name, i.name;
```

如果 SQL Server 版本或兼容级别导致 `STRING_AGG ... WITHIN GROUP` 不可用，可改用客户端导出或分表查询。

### 9.5 手工方式：主键和外键查询

```sql
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    kc.name AS constraint_name,
    kc.type_desc,
    STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS key_columns
FROM sys.key_constraints kc
JOIN sys.tables t
    ON kc.parent_object_id = t.object_id
JOIN sys.schemas s
    ON t.schema_id = s.schema_id
JOIN sys.index_columns ic
    ON kc.parent_object_id = ic.object_id
   AND kc.unique_index_id = ic.index_id
JOIN sys.columns c
    ON ic.object_id = c.object_id
   AND ic.column_id = c.column_id
WHERE s.name = 'dbo'
GROUP BY s.name, t.name, kc.name, kc.type_desc
ORDER BY t.name, kc.name;
```

```sql
SELECT
    s.name AS schema_name,
    parent_t.name AS table_name,
    fk.name AS foreign_key_name,
    parent_c.name AS column_name,
    ref_t.name AS referenced_table_name,
    ref_c.name AS referenced_column_name
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc
    ON fk.object_id = fkc.constraint_object_id
JOIN sys.tables parent_t
    ON fkc.parent_object_id = parent_t.object_id
JOIN sys.schemas s
    ON parent_t.schema_id = s.schema_id
JOIN sys.columns parent_c
    ON fkc.parent_object_id = parent_c.object_id
   AND fkc.parent_column_id = parent_c.column_id
JOIN sys.tables ref_t
    ON fkc.referenced_object_id = ref_t.object_id
JOIN sys.columns ref_c
    ON fkc.referenced_object_id = ref_c.object_id
   AND fkc.referenced_column_id = ref_c.column_id
WHERE s.name = 'dbo'
ORDER BY parent_t.name, fk.name;
```

### 9.6 单表变更后的快速确认 SQL

新增字段后：

```sql
SELECT
    c.name AS column_name,
    ty.name AS data_type,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    dc.definition AS default_definition
FROM sys.columns c
JOIN sys.types ty
    ON c.user_type_id = ty.user_type_id
LEFT JOIN sys.default_constraints dc
    ON c.default_object_id = dc.object_id
WHERE c.object_id = OBJECT_ID('dbo.amazon_listing_snapshot')
ORDER BY c.column_id;
```

新增索引后：

```sql
SELECT
    i.name AS index_name,
    i.is_unique,
    i.has_filter,
    i.filter_definition
FROM sys.indexes i
WHERE i.object_id = OBJECT_ID('dbo.amazon_listing_snapshot')
ORDER BY i.name;
```

## 10. 如何更新 `database_current_schema_spec.md`

执行 migration 并查询真实 schema 后，按以下顺序更新 spec：

1. 更新顶部版本号、更新时间和当前数据库状态。
2. 更新已执行 migration 列表。
3. 如果新增/修改表，更新“表清单与数据来源”。
4. 如果新增/修改索引，更新“索引清单”。
5. 如果字段变化，更新对应表的字段明细。
6. 如果入库状态变化，更新“已真实验证”或“当前限制”。
7. 明确写出哪些内容仍是限制，不要把未实现内容写成已完成。

必须遵守：

```text
current schema spec 只写真实状态，不写未来目标。
```

如果某个字段已经通过 migration 创建，但 repository 还没写入，可以这样写：

```text
字段已存在；repository/upsert 尚未实现。
```

如果某个字段只是 planned，不能写进 current schema spec，应写在相关 feature 文档的 migration 需求里。

## 11. 代码开发流程

设计和必要 migration 完成后，再进入代码。

### 11.1 Ingestion 功能推荐分层

新增 ingestion 功能时，参考 Ads 已验证模式：

```text
scripts/xxx.py
  -> ingestion service / dry-run builder
  -> parser
  -> schema guard / expected schema registry
  -> table mapping
  -> repository upsert
  -> Azure SQL
  -> sync_run_log / schema_validation_event
```

分层职责：

| 层 | 职责 |
|---|---|
| `scripts/` | 参数解析、日志、调用业务层；不要写复杂业务逻辑。 |
| `parsers/amazon/` | 把 raw file 解析成结构化 records。 |
| `ingestion/` | 字段映射、schema guard、dry-run preview、编排。 |
| `db/repositories/` | SQL MERGE/upsert、事务、统计 inserted/updated/skipped。 |
| `tests/` | 单元测试和必要集成测试。 |

### 11.2 Dry-run 优先

任何入库功能必须先支持 dry-run：

```text
raw file -> parsed rows -> mapped DB-ready rows -> preview JSON/JSONL -> schema validation result
```

Dry-run 不写数据库，但要暴露：

- 源文件数量。
- 源行数。
- 目标表准备写入行数。
- 字段缺失/新增情况。
- `requires_review`。
- preview 输出目录。

### 11.3 Execute 和幂等性

Execute 只有在 schema guard 通过后才能写库。

幂等性验收必须至少跑两次同一批数据：

```text
第一次 execute: inserted=N, updated=0 或符合预期
第二次 execute: inserted=0, updated=N/skipped=N
目标表总行数不增加
```

如果第二次仍 `inserted=N`，说明唯一键或 upsert 匹配条件错误，不能标记为完成。

## 12. Azure SQL 自动暂停/恢复处理规则

Azure SQL serverless 长时间没有 SQL 请求后可能自动暂停，恢复期间第一次 `pyodbc.connect()` 可能出现 `08001 Login timeout expired` 或 `Unable to complete login process due to delay in login response`。这不是业务 SQL 错误，但会影响自动化定时任务。

还需要区分另一类常见连接失败：Azure SQL Server firewall 未放行当前客户端 IP，例如 `40615` / `Client with IP address ... is not allowed to access the server`。这不是 idle/resume，不能靠 retry 解决，必须先放行 IP 或配置云端固定出站网络。

项目统一处理方式：

```text
get_connection()
  -> pyodbc.connect retry for known transient connection errors
  -> SELECT 1 warm-up query
  -> yield verified connection to migration / ingestion code
```

配置项：

```env
AZURE_SQL_CONNECT_MAX_ATTEMPTS='6'
AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS='5'
AZURE_SQL_CONNECT_RETRY_BACKOFF='1.8'
```

规则：

1. 自动化任务不要直接使用 `pyodbc.connect()`，必须使用项目的 `get_connection()`。
2. retry 只覆盖连接和 warm-up 阶段，不覆盖 parser、MERGE、migration batch 或业务 SQL。
3. 业务 SQL 出错时应按功能验收和 transaction 规则处理，不应盲目重试。
4. firewall/IP allowlist、账号密码、权限等非 transient 错误必须 fail fast，并输出明确错误；不要通过增加 retry 掩盖。
5. 如果连接长期失败，任务应失败并暴露日志，而不是静默跳过。

连接问题排查顺序见 `docs/database/azure_sql_connection_runbook.md`。

## 13. 验收流程

### 13.1 文档类变更验收

文档类变更完成后检查：

1. 是否更新了正确的 `docs/` 文件，而不是继续在旧 `requirements/` 里新增长期设计。
2. README / docs index 是否需要新增链接。
3. progress 是否记录了真实进度。
4. 是否没有把 planned 内容写成 implemented。
5. 是否没有修改已执行 migration。

### 13.2 代码类变更验收

至少运行：

```bash
PYTHONPATH=src pytest -q
python -m compileall -q scripts src tests
```

如果环境安装 Ruff：

```bash
ruff check src tests scripts
ruff format src tests scripts
```

### 13.3 数据库类变更验收

至少运行：

```bash
python scripts/run_sql_migration.py --file sql/migrations/NNN_xxx.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/NNN_xxx.sql
python scripts/test_azure_sql_connection.py --json
python scripts/test_azure_sql_connection.py --json --max-attempts 8 --retry-delay-seconds 8
python scripts/test_azure_sql_connection.py --list-tables
python scripts/check_database_status.py
```

并使用第 9 节 SQL 查询真实字段/索引后，再更新 spec。

### 13.4 Ingestion 功能验收

最低验收：

| 验收项 | 要求 |
|---|---|
| dry-run | 成功生成 preview，且 `requires_review=False` 或合理说明。 |
| schema guard | 记录 validation event；blocking error 不允许 execute。 |
| execute | 成功写入 Azure SQL。 |
| 幂等性 | 第二次同数据 execute 不重复插入。 |
| 行数检查 | 目标表行数符合预期。 |
| run log | `amazon_sync_run_log` 有 started/finished/status/rows。 |
| validation event | `amazon_schema_validation_event` 有结果，且无 blocking error。 |
| tests | 相关单元测试和全量测试通过。 |
| docs | feature 文档、progress、schema spec 已同步。 |

## 14. 进度记录规则

每批迭代结束后，更新：

```text
docs/project/progress_next_steps.md
```

Progress 文档只记录真实进展和近期计划，不写长篇设计。应该包括：

- 本批完成了什么。
- 是否改变真实数据库。
- 是否完成真实入库。
- 验收命令和关键结果。
- 当前非阻塞问题。
- 下一步建议。

不要在 progress 里复制大量字段映射；字段映射留在 feature 文档。

## 15. 输出交付规则

用户偏好：交付 **updated files only overlay package**，不要整包项目。

交付前应确认：

1. 只包含本次新增/修改文件。
2. 不包含 `.env`、`reports/raw/`、`runtime/`、真实 raw report、缓存文件。
3. 不包含整个项目源码包，除非用户明确要求。
4. 最终回复说明新增/更新文件清单和下一步建议。

## 16. AI 接手任务时的固定提示

后续把任务交给 AI 时，建议使用类似提示：

```text
请先阅读 README.md、docs/README.md、docs/project/iteration_workflow.md、docs/project/development_rules.md、docs/project/progress_next_steps.md、相关 feature 文档、docs/database/database_current_schema_spec.md。

本次任务只允许修改 <范围>。
不得修改已执行的 migration。
如果需要数据库变更，先说明与 current schema spec 的差异，再新增下一个编号的 migration。
如果 migration 执行成功，必须用真实 Azure SQL schema 查询结果更新 database_current_schema_spec.md。
完成后更新 progress_next_steps.md，并输出 updated files only overlay package。
```

## 17. 当前下一步建议

截至 2026-05-17，文档和数据库治理规则已经进入最终体系；Ads、Listing、Inventory、Sales & Traffic、Settlement、Orders、FBA Reimbursements 等 normalized ingestion 链路均已完成真实写库和第二次 execute 幂等性验证。下一步建议按本 SOP 先做 FBA Fee Preview 的数据库 migration，再进入代码实现：

```text
读取 docs/features/feature_fba_fee_preview_ingestion.md
-> 确认 009_add_fba_fee_preview_business_key.sql 已准备
-> 用户本地 dry-run / execute 009
-> 运行 export_database_schema_spec.py 导出 after_009_fba_fee_preview_business_key live schema
-> 更新 database_current_schema_spec.md
-> 开发 scripts/ingest_fba_fee_preview_report.py 专用入口
-> dry-run 验证 prepared_rows=8 requires_review=False
-> execute + 第二次 execute 幂等性验证
-> 更新 feature_fba_fee_preview_ingestion.md 和 progress_next_steps.md 为 Implemented
```

在进入 FBA Fee Preview 代码开发前，AI 应再次确认：

1. 数据源字段来自 `docs/data_access/sp_api_reports_catalog.md` 和 `docs/features/feature_fba_fee_preview_ingestion.md`。
2. 当前 `amazon_fba_fee_preview` 真实表尚未包含 `source_row_index`、`business_key_hash` 与唯一过滤索引；必须先执行 `009` 并导出 live schema。
3. `001-008` 已执行成功，不得回改；后续结构变化从 `009_xxx.sql` 开始。
4. 所有真实 SQL 入口必须使用 `get_connection()`，不得绕开连接 warm-up retry。
5. 本轮是否允许改代码和新增测试。
