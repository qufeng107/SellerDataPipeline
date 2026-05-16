# ADR-004: Current Schema Spec 必须来自真实数据库结构

> 状态：Accepted  
> 日期：2026-05-16  
> 决策范围：Azure SQL schema spec、migration 执行后验收、数据库文档维护

## 背景

项目当前使用 Azure SQL `amazon_ops` 作为 normalized 数据库，并已经执行：

```text
001_create_core_tables.sql -> 29/29 batches
002_create_indexes.sql -> 54/54 batches
003_add_listing_snapshot_business_key_hash.sql -> 3/3 batches
```

数据库当前真实状态记录在：

```text
docs/database/database_current_schema_spec.md
```

但数据库 spec 如果只靠阅读 migration 文件人工推断，可能出现偏差：

1. migration 可能只执行了一部分后失败。
2. SQL Server 实际字段类型、长度、默认约束名称与预期不同。
3. 过滤索引、唯一索引、默认值、可空性容易遗漏。
4. 旧 migration 文件不能回改，注释可能滞后。
5. 未来可能有人在数据库中手动执行 SQL，导致真实库与文档不一致。

因此需要明确：current schema spec 是真实数据库状态记录，不是设计草案，也不是 migration 文件的简单复制。

## 决策

`docs/database/database_current_schema_spec.md` 必须基于真实 Azure SQL schema 查询结果维护。

执行任何数据库 migration 后，必须：

1. 连接 Azure SQL `amazon_ops`。
2. 查询真实表、字段、索引、约束。
3. 确认 migration 目标已经实际存在。
4. 再更新 `database_current_schema_spec.md`。

禁止在 migration 未执行前，把目标结构写入 current schema spec。禁止只凭 migration 文件内容更新 spec。

## 原因

1. **事实优先**：current schema spec 的职责是记录真实状态，不是未来设计。
2. **避免半执行偏差**：如果 migration 部分执行失败，真实库才是最终判断依据。
3. **提高 AI 可靠性**：AI 读取 spec 时可以相信它代表当前数据库，而不是计划。
4. **支持后续差异分析**：新功能开发时可以用 spec 与 feature 设计对比，决定是否需要新 migration。
5. **降低生产风险**：数据库结构变更必须经过执行和验证闭环。

## 实施规则

每次 migration 执行成功后，按以下顺序操作：

```text
1. 运行 migration dry-run
2. 正式执行 migration
3. 运行连接和表检查脚本
4. 执行 sys.tables / sys.columns / sys.indexes 查询
5. 确认新增表、字段、索引、约束真实存在
6. 更新 database_current_schema_spec.md
7. 更新相关 feature 文档
8. 更新 progress_next_steps.md
```

参考查询写入：

```text
docs/project/iteration_workflow.md
```

## Spec 中允许写什么

允许写入：

- 已存在的表。
- 已存在的字段、类型、可空性、默认值。
- 已存在的索引、唯一性、过滤条件。
- 已执行 migration 列表。
- 已真实验证的入库状态。
- 已知限制，例如“字段已存在，但 repository 尚未实现”。

## Spec 中禁止写什么

禁止写入为事实：

- 计划新增但未执行的字段。
- 计划新增但未执行的索引。
- 尚未执行的 migration。
- 尚未开发的 repository。
- 未来可能拆分的表。
- 未验证的入库状态。

这些内容应写入：

```text
docs/features/feature_*.md
```

或：

```text
docs/data_access/*.md
```

## 后果

正面影响：

- current schema spec 更可信。
- 数据库和文档不容易长期偏移。
- AI 可以稳定按 spec 判断下一步是否需要 migration。
- 每次结构变化都有明确验证路径。

代价：

- migration 执行后需要额外查询和文档同步。
- 不能只凭 SQL 文件快速更新 spec。
- 后续最好补充自动导出 schema 的脚本，减少人工复制错误。

## 后续建议

后续可新增脚本：

```text
scripts/export_database_schema_spec.py
```

用于从 Azure SQL 导出：

```text
表清单
字段结构
索引清单
主键/外键/default constraints
```

输出为 JSON 或 Markdown 草稿，再由 AI / 开发者审查后更新 `database_current_schema_spec.md`。

在该脚本实现前，按 `docs/project/iteration_workflow.md` 中的 SQL 查询人工读取真实 schema。

## 状态

Accepted。
