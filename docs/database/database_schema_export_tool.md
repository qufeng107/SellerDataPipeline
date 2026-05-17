# Azure SQL 真实 Schema 导出工具

> 更新时间：2026-05-16  
> 文档定位：说明如何从真实 Azure SQL `amazon_ops` 读取当前表、字段、索引和约束，并生成可审查的 schema export。该导出结果用于辅助更新 `docs/database/database_current_schema_spec.md`，但不能自动替代人工维护的 current schema spec。

## 1. 为什么需要这个工具

项目已经规定：`database_current_schema_spec.md` 必须来自真实 Azure SQL，而不能只根据 migration 文件推断。

此前更新 spec 主要依赖人工 SQL 查询。为了降低遗漏字段、索引、约束的风险，新增：

```text
scripts/export_database_schema_spec.py
```

该脚本通过项目统一连接层 `get_connection()` 连接 Azure SQL，因此会自动执行：

```text
pyodbc.connect retry
-> SELECT 1 warm-up
-> 读取系统 catalog views
```

如果失败信息包含 `40615` 或 `Client with IP address ... is not allowed to access the server`，说明当前公网 IP 没有被 Azure SQL Server firewall 放行。这不是 schema export 工具问题，也不是 idle/resume；先按 `azure_sql_connection_runbook.md` 处理网络 allowlist。

如果失败信息包含 `ODBC SQL type ... is not yet supported`，通常说明某个 system catalog 查询返回了 pyodbc 无法直接 fetch 的 SQL Server driver-specific 类型。当前已知案例是 `sys.identity_columns.seed_value / increment_value` 的 `sql_variant` 类型；项目查询必须先把这类字段 cast/convert 成普通文本或数字类型，再进入 `rows_to_dicts()`。

适合在以下场景使用：

1. migration 执行成功后，导出真实 schema，用于更新 current schema spec。
2. 怀疑 `database_current_schema_spec.md` 与真实数据库偏移时，导出对比。
3. 自动化任务上线前，保存一次数据库结构快照。
4. 让后续 AI 迭代时先看真实 schema export，再决定是否需要新 migration。

## 2. 基本命令

默认导出 Markdown 和 JSON：

```bash
python scripts/export_database_schema_spec.py
```

默认输出目录：

```text
runtime/schema_exports/
```

默认文件名类似：

```text
azure_sql_schema_20260516_233000.md
azure_sql_schema_20260516_233000.json
```

只导出 Markdown：

```bash
python scripts/export_database_schema_spec.py --format markdown
```

只导出 JSON：

```bash
python scripts/export_database_schema_spec.py --format json
```

指定输出目录和前缀：

```bash
python scripts/export_database_schema_spec.py \
  --out-dir runtime/schema_exports \
  --output-prefix amazon_ops_after_004
```

直接打印 Markdown 预览：

```bash
python scripts/export_database_schema_spec.py --stdout-markdown
```

包含当前行数：

```bash
python scripts/export_database_schema_spec.py --include-row-counts
```

行数来自 `sys.dm_db_partition_stats`，适合审计和快速检查；如果只想看结构，可以不加该参数。

## 3. 导出内容

脚本读取以下 SQL Server system catalog / DMV：

| 来源 | 用途 |
|---|---|
| `sys.tables` + `sys.schemas` | 用户表清单、create/modify date。 |
| `sys.columns` + `sys.types` | 字段顺序、字段名、数据类型、长度、精度、可空。 |
| `sys.identity_columns` | identity seed / increment；这些 catalog 字段是 `sql_variant`，查询中必须 `CONVERT(nvarchar(100), ...)` 后再给 pyodbc 读取。 |
| `sys.default_constraints` | 默认值约束名和定义。 |
| `sys.indexes` + `sys.index_columns` | 索引、唯一性、过滤条件、key columns、included columns。 |
| `sys.key_constraints` | 主键和唯一约束。 |
| `sys.foreign_keys` + `sys.foreign_key_columns` | 外键、引用表和引用字段。 |
| `sys.dm_db_partition_stats` | 可选表行数。 |

## 4. 如何用于更新 current schema spec

数据库变更后的推荐流程：

```text
1. 新增并执行 sql/migrations/NNN_xxx.sql
2. 运行 scripts/export_database_schema_spec.py --output-prefix after_NNN_xxx
3. 打开生成的 markdown/json，确认目标字段、索引、约束真实存在
4. 对比 docs/database/database_current_schema_spec.md
5. 人工更新 current schema spec 的：
   - 已执行 migration 列表
   - 表清单
   - 索引清单
   - 涉及表的字段明细
   - 当前真实入库状态或限制
6. 更新 progress_next_steps.md 和相关 feature 文档
```

注意：**export 文件不是正式 spec**。正式 spec 仍然是：

```text
docs/database/database_current_schema_spec.md
```

原因是 schema export 只能提供数据库事实，无法完整表达：

1. 字段的业务说明。
2. 字段来自哪个 Amazon report / Ads report。
3. 某表当前是否已有真实入库验证。
4. 某些字段为什么暂时保留或暂不使用。
5. 功能设计中的弃置项和后续优化项。

## 5. 和手工 SQL 查询的关系

`docs/project/iteration_workflow.md` 里保留了手工 SQL 查询模板。导出工具不废弃这些 SQL，而是提供更方便、更一致的默认方式。

推荐优先级：

```text
日常更新 spec -> 先用 export_database_schema_spec.py
需要排查特殊问题 -> 再用手工 SQL 精查
```

例如，只检查某个字段是否存在时，手工 SQL 仍然更快；但每次 migration 后同步 spec，应优先跑完整导出。

## 6. 安全和限制

1. 该脚本只读系统 catalog，不修改数据库。
2. 该脚本不导出业务数据内容。
3. 如果使用 `--include-row-counts`，只导出表级行数，不导出行内容。
4. 该脚本依赖 `.env` 中的 Azure SQL 配置。
5. Catalog 查询必须避免直接返回 pyodbc 不支持的 SQL Server 特殊类型，例如 `sql_variant`。
6. 输出到 `runtime/`，默认不提交到 Git。
7. 如需把某次导出作为审计附件提交，必须确认不含敏感经营数据；结构信息通常可以提交，但仍建议按需保留。

## 7. 后续优化

后续可以继续增强：

1. 增加 `--compare-with docs/database/database_current_schema_spec.md` 的半自动差异提示。
2. 增加 `--table dbo.amazon_listing_snapshot` 只导出单表。
3. 增加 GitHub Action 中的 schema drift 检查。
4. 生成更接近 `database_current_schema_spec.md` 格式的草稿段落。

当前版本先保持简单可靠：读取真实 schema、输出 markdown/json、辅助人工或 AI 更新正式 spec。
