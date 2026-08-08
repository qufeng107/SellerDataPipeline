# Feature: <功能名称>

> 文档状态：Template  
> 负责人：<owner / AI / 待定>  
> 更新时间：YYYY-MM-DD  
> 功能状态：Proposed / Planned / Implementing / Implemented / Deprecated  
> 相关数据接入文档：`docs/data_access/...`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`

---

## 1. 功能摘要

用 3-5 句话说明这个功能是什么、解决什么问题、当前做到什么程度。

示例：

```text
本功能负责把 Amazon Ads spCampaigns / spTargeting / spSearchTerm / spAdvertisedProduct raw reports 转换为四张 Sponsored Products 日维度 normalized 表。功能支持 dry-run preview、schema guard、Azure SQL MERGE/upsert 和幂等性验证。
```

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 未开始 / 已确认 / 待复核 |
| 数据源取样 | 未开始 / 已完成 / 不适用 |
| Parser | 未开始 / 开发中 / 已完成 |
| Dry-run preview | 未开始 / 开发中 / 已完成 |
| Schema guard | 未开始 / 开发中 / 已完成 |
| Repository/upsert | 未开始 / 开发中 / 已完成 |
| Azure SQL execute | 未开始 / 已验证 / 不适用 |
| 幂等性验证 | 未开始 / 已通过 / 不适用 |
| 单元测试 | 未开始 / 已完成 / 待补强 |
| 文档同步 | 未开始 / 已完成 / 待补强 |

功能整体状态只能使用：

```text
Proposed      # 提出想法，尚未排期
Planned       # 已确认要做，设计未完成或待开发
Implementing  # 正在开发或验证
Implemented   # 已实现并通过验收
Deprecated    # 已弃置，不再推进
```

## 3. 业务目标

说明这个功能对电商运营的业务价值。

应回答：

1. 谁会用这个功能？
2. 它帮助解决什么运营问题？
3. 输出结果会影响什么决策？
4. 对当前公司阶段的优先级如何？

避免只写技术动作，例如“把 A 表写入数据库”。要说明为什么要写入。

## 4. 范围与非范围

### 4.1 本功能包含

- <包含项 1>
- <包含项 2>
- <包含项 3>

### 4.2 本功能不包含

- <非范围 1>
- <非范围 2>
- <非范围 3>

非范围很重要，用于防止后续 AI 把多个功能混在一起改。

## 5. 输入数据

列出本功能使用的所有数据源。每一项都应能在 `docs/data_access/` 中找到对应说明。

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports / Amazon Ads / Seller Central | `<report_type>` | txt/json/csv/xlsx | 未取样 / 已取样 | 未解析 / 已解析 |  |

如果本功能不直接接入外部数据，而是读取 Azure SQL 派生指标，也要写明读取哪些表。

## 6. 输出结果

说明本功能最终产出什么。

可能包括：

- Azure SQL normalized 表。
- 审计记录。
- Excel 报表。
- Markdown/JSON 输出。
- 邮件通知。
- 运营建议。

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Azure SQL table | `dbo.xxx` |  |
| runtime preview | `runtime/...` |  |
| Excel report | `reports/generated/...` |  |

## 7. 处理流程

用步骤或流程图说明完整链路。

```text
raw input
  -> parser
  -> field normalization
  -> schema guard
  -> dry-run preview
  -> repository upsert
  -> audit log
  -> final output
```

每一步都应说明：

1. 输入是什么。
2. 输出是什么。
3. 失败时怎么处理。
4. 是否写数据库。

## 8. 字段映射

### 8.1 源字段到标准字段

| 源字段 | 标准字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|---|
| `<source_field>` | `<normalized_field>` | string/int/decimal/date | yes/no |  |

### 8.2 标准字段到数据库字段

| 标准字段 | 目标表 | 目标字段 | 类型 | 转换规则 |
|---|---|---|---|---|
| `<normalized_field>` | `dbo.xxx` | `xxx` | NVARCHAR/DECIMAL/DATE |  |

字段映射必须尽量避免只写“同名映射”。如果有日期、金额、百分比、空值、枚举映射，要写清楚规则。

## 9. 目标数据表设计

如果目标表已经存在，引用 `docs/database/database_current_schema_spec.md`。

如果目标表尚不存在或需要新增字段，只在这里写**设计意图**，不要把它写入 current schema spec，直到 migration 真实执行成功。

### 9.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.xxx` | yes/no |  | insert / update / merge / read-only |

### 9.2 业务主键 / 幂等键

说明如何判断同一条业务记录。

示例：

```text
business_key = profile_id + report_date + campaign_id
business_key_hash = sha256(canonical JSON of business key)
```

### 9.3 新 migration 需求

如果需要数据库变化，写清楚：

| 变化 | 原因 | migration 文件 | 状态 |
|---|---|---|---|
| 新增字段 `xxx` |  | `00N_xxx.sql` | planned / executed |

注意：migration 执行成功前，不要更新 current schema spec。

## 10. 幂等性设计

必须说明重复执行同一批数据时会发生什么。

应回答：

1. 重复执行是否安全？
2. 根据什么唯一键或业务键判断 insert/update？
3. 如果源文件同一业务键但指标变化，是 update 还是 skip？
4. 如果同一 raw file 重复处理，是否会重复插入？
5. 如何验证幂等性？

验收示例：

```text
第一次 execute: inserted=N, updated=0
第二次 execute: inserted=0, updated=N 或 skipped=N
目标表总行数保持不变
```

## 11. Schema guard 与异常处理

说明字段漂移和异常数据如何处理。

| 场景 | 处理方式 | 是否阻塞入库 | 是否记录 validation event |
|---|---|---|---|
| 缺少必需字段 | 默认 `requires_review=True` | yes | yes |
| 出现新增字段 | 默认 warning，保留 drift 证据并继续处理 | no | yes |
| 已知非关键字段缺失 | 默认 warning/info | no | yes/no |
| 空文件 | 按该 report 的业务语义明确设计 | yes/no | yes |
| 数字解析失败 | 关键字段默认阻断 | yes | yes |
| 日期解析失败 | 关键字段默认阻断 | yes | yes |

项目默认遵循 `ADR-013-schema-guard-compatibility-policy.md`：

- `expected_fields` 是已知字段目录，不等于全部必需字段。
- `required_fields` 只包含安全入库所需的最小业务契约。
- Amazon 新增 unknown field 属于 additive drift，默认 non-blocking，但必须留 validation event。
- warning 与 blocking 解耦；只有真正需要人工处理后才能安全继续时才设置 `requires_review=True`。
- 如某功能需要比该默认策略更严格，必须在 feature 文档中写明业务原因。

必须明确说明何时设置：

```text
requires_review=True
```

## 12. 审计与可追溯性

说明需要写入哪些审计表和字段。

| 审计对象 | 表/字段 | 说明 |
|---|---|---|
| 任务运行 | `amazon_sync_run_log` | started_at, finished_at, status, rows_read, rows_written 等 |
| schema 检查 | `amazon_schema_validation_event` | validation_status, requires_review, message 等 |
| raw 文件 | `amazon_raw_report_file` | 后续应记录 raw file path/hash/size |
| 源行追溯 | `source_report_id/source_raw_file_id/source_row_hash` | normalized 表中的来源追溯字段 |

如果当前实现有审计缺口，也要明确写入“后续优化”。

## 13. 命令行入口

列出用户如何运行本功能。

```bash
python scripts/xxx.py --dry-run
python scripts/xxx.py --execute
```

参数说明：

| 参数 | 是否必需 | 默认值 | 说明 |
|---|---|---|---|
| `--marketplace-id` | yes/no |  |  |
| `--profile-id` | yes/no |  |  |
| `--execute` | no | false | 不加时只 dry-run |

## 14. 相关代码路径

| 类型 | 路径 | 说明 |
|---|---|---|
| script | `scripts/xxx.py` |  |
| parser | `src/seller_data_pipeline/parsers/...` |  |
| ingestion | `src/seller_data_pipeline/ingestion/...` |  |
| repository | `src/seller_data_pipeline/db/repositories/...` |  |
| tests | `tests/...` |  |

## 15. 测试计划

列出本功能必须通过的测试。

```bash
PYTHONPATH=src pytest -q tests/unit/...
PYTHONPATH=src pytest -q
python -m compileall -q scripts src tests
```

如果需要真实 Azure SQL 或 Amazon API，必须标明是 integration/manual test，不应放入默认单元测试。

## 16. 验收标准

功能完成必须满足可验证标准。

示例：

1. dry-run 成功，生成 preview。
2. `requires_review=False` 或 warning 可解释。
3. execute 成功写入 Azure SQL。
4. 重复 execute 幂等性通过。
5. 目标表行数符合预期。
6. `amazon_sync_run_log` 记录本次任务。
7. `amazon_schema_validation_event` 记录 schema 检查结果。
8. 单元测试通过。
9. 文档状态更新为 `Implemented`。

## 17. 当前实现状态

按日期记录真实进展，不要写空泛描述。

| 日期 | 进展 | 证据/命令 | 备注 |
|---|---|---|---|
| YYYY-MM-DD |  |  |  |

## 18. 后续优化

列出非阻塞但值得后续做的事项。

- <优化项 1>
- <优化项 2>

## 19. 弃置记录

如果某些方案被放弃，必须保留记录，避免未来重复走弯路。

| 日期 | 弃置内容 | 原因 | 替代方案 |
|---|---|---|---|
| YYYY-MM-DD |  |  |  |
