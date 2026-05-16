# ADR-002: 已执行 SQL Migration 不允许修改

> 状态：Accepted  
> 日期：2026-05-16  
> 决策范围：Azure SQL migration、数据库真实状态、schema spec 维护

## 背景

SellerDataPipeline 已经在 Azure SQL `amazon_ops` 上成功执行：

```text
sql/migrations/001_create_core_tables.sql -> 29/29 batches
sql/migrations/002_create_indexes.sql -> 54/54 batches
sql/migrations/003_add_listing_snapshot_business_key_hash.sql -> 3/3 batches
```

执行后数据库有 28 张用户表，Amazon Ads 四张 Sponsored Products 日表已经完成真实入库和幂等性验证；Listing 表已具备 `business_key_hash` 幂等键和唯一过滤索引。

在后续迭代中，AI 或开发者可能会发现：

- migration 文件里的注释有滞后。
- 某些字段设计需要改进。
- 某些表需要新增字段或索引。
- 某些历史 SQL 看起来可以“顺手修一下”。

如果直接修改已执行 migration，会导致代码仓库中的 migration 历史与真实 Azure SQL 执行历史不一致，使后续环境重建、问题排查和 AI 理解项目时出现混乱。

## 决策

已在真实 Azure SQL 环境执行成功的 migration 文件不允许修改。

当前已锁定：

```text
sql/migrations/001_create_core_tables.sql
sql/migrations/002_create_indexes.sql
sql/migrations/003_add_listing_snapshot_business_key_hash.sql
```

任何数据库结构变化都必须新增 migration：

```text
sql/migrations/004_xxx.sql
sql/migrations/005_xxx.sql
...
```

即使发现 `001/002/003` 中存在注释滞后或命名不够理想，也不回改历史文件。真实状态以以下文档为准：

```text
docs/database/database_current_schema_spec.md
docs/project/progress_next_steps.md
```

## 原因

1. **保护历史可追溯性**：migration 是数据库演进历史，不只是最终 schema 文件。
2. **避免环境偏移**：真实 Azure SQL 已执行的 SQL 和仓库中的历史 migration 必须保持可解释。
3. **降低 AI 误改风险**：AI 容易直接编辑旧 SQL 文件；明确禁止可以减少破坏性修改。
4. **支持增量部署**：生产或类生产数据库只能通过新增 migration 安全演进。
5. **便于审计**：每个结构变化都有独立文件、原因、执行记录和 spec 更新。

## 后果

正面影响：

- 数据库演进历史清晰。
- current schema spec 可以准确记录真实状态。
- 后续新增字段、索引、约束都有明确版本。
- 出错时可以定位是哪一个 migration 引入。

代价：

- 即使只是小改动，也要新增 migration。
- 旧 migration 文件中的注释可能不完全反映最新状态。
- 需要维护 migration policy 和 current schema spec。

## 实施规则

1. 新增字段：新建下一个递增编号 migration，例如 `004_add_xxx_column.sql`。
2. 新增索引：新建 `00N_create_xxx_index.sql` 或合并到相关 migration。
3. 修复字段类型：新建 migration，明确数据迁移和兼容策略。
4. 删除字段或表：必须先在 feature 文档中说明影响，谨慎执行。
5. 执行成功后更新：
   - `docs/database/database_current_schema_spec.md`
   - 相关 `docs/features/feature_*.md`
   - `docs/project/progress_next_steps.md`

## 示例

如果要给 `amazon_sync_run_log` 增加 inserted/updated 拆分字段，不允许修改 `001_create_core_tables.sql`，而应新增：

```text
sql/migrations/004_add_sync_run_upsert_counts.sql
```

示例内容：

```sql
IF COL_LENGTH('dbo.amazon_sync_run_log', 'rows_inserted') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_sync_run_log
    ADD rows_inserted INT NOT NULL
        CONSTRAINT DF_amazon_sync_run_log_rows_inserted DEFAULT (0);
END;
GO
```

## 状态

Accepted。
