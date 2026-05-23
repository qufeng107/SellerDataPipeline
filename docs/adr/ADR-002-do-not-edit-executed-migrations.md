# ADR-002: 已执行 SQL Migration 不允许修改

> 状态：Accepted  
> 日期：2026-05-16  
> 最近更新：2026-05-18  
> 决策范围：Azure SQL migration、数据库真实状态、schema spec 维护

## 背景

SellerDataPipeline 已经在 Azure SQL `amazon_ops` 上执行了一系列 migration。migration 文件是数据库演进历史，而不是“可随时改成最终样子”的 schema 草稿。

如果直接修改已执行 migration，会导致代码仓库中的 migration 历史与真实 Azure SQL 执行历史不一致，使后续环境重建、问题排查和 AI 理解项目时出现混乱。

## 决策

已在真实 Azure SQL 环境执行成功的 migration 文件不允许修改。

当前已锁定：

```text
sql/migrations/001_create_core_tables.sql
sql/migrations/002_create_indexes.sql
sql/migrations/003_add_listing_snapshot_business_key_hash.sql
sql/migrations/004_add_inventory_daily_business_key_hash.sql
sql/migrations/005_add_sales_traffic_business_key_hashes.sql
sql/migrations/006_add_settlement_transaction_business_key.sql
sql/migrations/007_add_order_item_business_key.sql
sql/migrations/008_add_fba_reimbursement_business_key.sql
sql/migrations/009_add_fba_fee_preview_business_key.sql
sql/migrations/010_add_promotion_coupon_business_keys.sql
sql/migrations/011_add_inventory_ledger_business_keys.sql
sql/migrations/012_create_ingestion_job_config.sql
```

任何新的数据库结构变化都必须继续新增后续 migration。当前无已准备但尚未执行的 migration；后续从 `013_xxx.sql` 开始。

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

1. 新增字段或表：新建下一个递增编号 migration。
2. 新增索引：新建 `00N_create_xxx_index.sql` 或合并到相关新增 migration。
3. 修复字段类型：新建 migration，明确数据迁移和兼容策略。
4. 删除字段或表：必须先在 feature 文档中说明影响，谨慎执行。
5. 执行成功后更新：
   - `docs/database/database_current_schema_spec.md`
   - 相关 `docs/features/feature_*.md`
   - `docs/project/progress_next_steps.md`

## 示例

如果要给 `amazon_sync_run_log` 增加 inserted/updated 拆分字段，不允许修改 `001_create_core_tables.sql`，而应新增：

```text
sql/migrations/013_add_sync_run_upsert_counts.sql
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

## 当前状态

Accepted。
