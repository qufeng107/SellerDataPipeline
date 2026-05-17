# SellerDataPipeline 数据库 Migration 与 Schema Spec 维护规则

> 更新时间：2026-05-17  
> 文档定位：定义 Azure SQL 表结构变更、migration 编写、执行、验证和文档同步规则。当前真实表结构见 `docs/database/database_current_schema_spec.md`。

## 1. 核心原则

1. **已执行 migration 不允许修改**。已经在 Azure SQL `amazon_ops` 成功执行的 SQL 文件是历史事实。
2. **任何结构变化必须新增 migration**，例如 Inventory 幂等键已使用 `004_add_inventory_daily_business_key_hash.sql`；Sales & Traffic 幂等键已通过 `005_add_sales_traffic_business_key_hashes.sql` 执行成功并纳入当前真实 schema。
3. **current schema spec 只记录真实状态**。migration 未执行前，不得把目标结构写入 `database_current_schema_spec.md`。
4. **功能设计先于 migration**。新增表或字段前，先在对应 `docs/features/feature_*.md` 写清楚业务原因、字段含义和验收标准。
5. **migration 执行后必须更新 spec 和 progress**。
6. **所有入库表必须考虑幂等性、来源追溯和审计字段**。
7. **schema spec 必须来自真实 Azure SQL 查询结果**，不能只凭 migration 文件推断；migration 后优先运行 `scripts/export_database_schema_spec.py` 导出 live schema snapshot。
8. **执行真实 SQL 前必须通过连接层 warm-up**。所有 migration / ingestion 应使用 `get_connection()`，让连接层先完成 retry 和 `SELECT 1` 预热。

## 2. 当前已执行 migration

截至 2026-05-17，已执行成功：

| 文件 | 状态 | 执行结果 |
|---|---|---|
| `sql/migrations/001_create_core_tables.sql` | executed | 29/29 batches |
| `sql/migrations/002_create_indexes.sql` | executed | 54/54 batches |
| `sql/migrations/003_add_listing_snapshot_business_key_hash.sql` | executed | 3/3 batches；为 `amazon_listing_snapshot` 增加 `business_key_hash` 和唯一过滤索引，支持 Listing 入库幂等 upsert |
| `sql/migrations/004_add_inventory_daily_business_key_hash.sql` | executed | 3/3 batches；为 `amazon_inventory_daily` 增加 `business_key_hash` 和唯一过滤索引，支持 Inventory 入库幂等 upsert |
| `sql/migrations/005_add_sales_traffic_business_key_hashes.sql` | executed | 5/5 batches；为 `amazon_sales_traffic_daily` 和 `amazon_sales_traffic_asin_daily` 增加 `business_key_hash` 和唯一过滤索引，支持 Sales & Traffic 入库幂等 upsert |
| `sql/migrations/006_add_settlement_transaction_business_key.sql` | executed | 4/4 batches；为 `amazon_settlement_transaction` 增加 `source_row_index`、`business_key_hash` 和唯一过滤索引，支持 Settlement 入库幂等 upsert |
| `sql/migrations/007_add_order_item_business_key.sql` | executed | 4/4 batches；为 `amazon_order_item` 增加 `source_row_index`、`business_key_hash` 和唯一过滤索引，支持 Orders 入库幂等 upsert |
| `sql/migrations/008_add_fba_reimbursement_business_key.sql` | executed | 4/4 batches；为 `amazon_fba_reimbursement` 增加 `source_row_index`、`business_key_hash` 和唯一过滤索引，支持 FBA Reimbursements 入库幂等 upsert |

以上 executed 文件后续不允许回改。即使发现注释滞后，也以 `docs/project/progress_next_steps.md` 和 `docs/database/database_current_schema_spec.md` 记录的真实执行状态为准。

## 2.1 当前已准备但尚未执行的 migration

| 文件 | 状态 | 说明 |
|---|---|---|
| `sql/migrations/009_add_fba_fee_preview_business_key.sql` | executed; locked | 为 `amazon_fba_fee_preview` 增加 `source_row_index`、`business_key_hash` 和唯一过滤索引；已执行并同步 current schema spec。 |

`009_add_fba_fee_preview_business_key.sql` 已执行成功并锁定；后续新结构变化从 `010_xxx.sql` 开始。

## 3. Migration 命名规则

新 migration 使用三位递增编号：

```text
sql/migrations/009_add_fba_fee_preview_business_key.sql  # executed; locked
sql/migrations/010_xxx.sql
sql/migrations/011_xxx.sql
```

命名要求：

- 编号连续递增。
- 文件名使用小写 snake_case。
- 文件名描述业务变化，而不是写“fix”或“update”。
- 一个 migration 尽量只做一类相关变化。

## 4. Migration 文件结构

建议结构：

```sql
-- SellerDataPipeline migration 006: add settlement transaction business key.
-- Created: 2026-xx-xx
-- Status: pending until executed against Azure SQL amazon_ops.
-- Reason: <why this change is needed>

/* =========================================================
   1. Add columns
   ========================================================= */

IF COL_LENGTH('dbo.amazon_sync_run_log', 'rows_inserted') IS NULL
BEGIN
    ALTER TABLE dbo.amazon_sync_run_log
    ADD rows_inserted INT NOT NULL CONSTRAINT DF_amazon_sync_run_log_rows_inserted DEFAULT (0);
END;
GO

/* =========================================================
   2. Add indexes
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.amazon_sync_run_log')
      AND name = 'IX_example'
)
BEGIN
    CREATE INDEX IX_example ON dbo.amazon_sync_run_log (job_name);
END;
GO
```

## 5. 可重复执行设计

Migration 应尽量具备防重复执行能力。

常用检查方式：

| 变更 | 推荐检查 |
|---|---|
| 新建表 | `IF OBJECT_ID('dbo.table_name', 'U') IS NULL` |
| 新增字段 | `IF COL_LENGTH('dbo.table_name', 'column_name') IS NULL` |
| 新增索引 | 查询 `sys.indexes` |
| 新增约束 | 查询 `sys.default_constraints` / `sys.key_constraints` |
| 新增 seed | 使用唯一键判断 `IF NOT EXISTS` |

避免直接写不可重复执行的裸 `CREATE TABLE`、`ALTER TABLE ADD`、`CREATE INDEX`。

## 6. 执行流程

### 6.1 开发前

1. 阅读相关 feature 文档。
2. 阅读 `database_current_schema_spec.md`。
3. 明确当前真实结构与目标结构的差异。
4. 在 feature 文档中写清 migration 需求。

### 6.2 本地/执行前检查

先 dry-run 查看 batches：

```bash
python scripts/run_sql_migration.py --file sql/migrations/010_xxx.sql --dry-run --show-batches
```

如果 dry-run 输出的 batch 数异常，先不要执行。dry-run 不连接数据库；它只能验证 SQL 文件拆分结果，不能唤醒或检查 Azure SQL 在线状态。

### 6.3 执行 migration

执行前可以先用连接测试唤醒/确认 Azure SQL；连接层也会在 `run_sql_migration.py` 内自动 retry 并执行 `SELECT 1` warm-up。注意：如果错误是 `40615` / 当前 IP 未被 Azure SQL Server firewall 放行，retry 不会解决，需先按 `docs/database/azure_sql_connection_runbook.md` 放行 IP。

```bash
python scripts/test_azure_sql_connection.py --json
python scripts/test_azure_sql_connection.py --json --max-attempts 8 --retry-delay-seconds 8
```

然后执行 migration：

```bash
python scripts/run_sql_migration.py --file sql/migrations/010_xxx.sql
```

执行成功后，立即检查数据库状态：

```bash
python scripts/test_azure_sql_connection.py --json
python scripts/test_azure_sql_connection.py --list-tables
python scripts/check_database_status.py
```

随后优先运行 live schema 导出脚本，从 Azure SQL 系统 catalog 读取真实 schema：

```bash
python scripts/export_database_schema_spec.py --output-prefix after_009_fba_fee_preview_business_key --include-row-counts
```

该脚本会读取 `sys.tables`、`sys.columns`、`sys.indexes`、`sys.key_constraints`、`sys.foreign_keys` 等真实数据库信息。必要时再按照 `docs/project/iteration_workflow.md` 中的手工 SQL 精查。只有确认字段/索引/约束真实存在后，才能更新 `database_current_schema_spec.md`。

如 migration 失败：

1. 不要假设部分执行已经全部回滚。
2. 先确认失败前哪些 batch 已执行。
3. 根据真实数据库状态写修复 migration。
4. 不要直接修改已经部分执行过的 migration 后重新伪装为同一版本。

## 7. 执行后文档同步

Migration 执行成功后，必须同步更新：

1. `docs/database/database_current_schema_spec.md`
   - 表清单
   - 字段结构
   - 索引清单
   - 数据来源说明
   - 已执行 migration 列表
2. 对应 `docs/features/feature_*.md`
   - migration 状态
   - 当前实现状态
   - 验收结果
3. `docs/project/progress_next_steps.md`
   - 新增里程碑或当前进度
   - 下一步变化
4. 必要时更新根目录 `README.md`
   - 仅当常用命令、当前阶段或文档入口变化时更新

## 8. Schema Spec 维护规则

`database_current_schema_spec.md` 只记录真实 Azure SQL 当前状态。详细 SOP 见：

```text
docs/project/iteration_workflow.md
```

对应架构决策见：

```text
docs/adr/ADR-004-database-spec-from-live-schema.md
```

允许写：

- 已存在的表。
- 已存在的字段。
- 已存在的索引。
- 已执行成功的 migration。
- 已真实验证的入库状态。
- 已知限制，例如某字段尚未存在。

不允许写成事实：

- 计划新增但未执行的字段。
- 计划新增但未执行的索引。
- 未来可能拆分的表。
- 尚未开发的 repository。

未执行的设计只能写在 feature 文档或 data access 文档中。

### 8.1 更新 spec 的最低步骤

1. 记录 migration 文件名和执行结果。
2. 优先运行 `scripts/export_database_schema_spec.py` 导出 live schema snapshot。
3. 查询或导出真实字段结构，确认类型、长度、可空、默认值。
4. 查询或导出真实索引结构，确认唯一性、字段顺序、过滤条件。
5. 如涉及主键/外键/default constraints，查询或导出约束。
6. 更新 spec 中的表清单、索引清单、字段明细和当前限制。
7. 不把未实现 repository、未执行 migration、未验证入库状态写成事实。

## 9. 表设计基本约定

### 9.1 主键

业务表通常使用数据库自增 `id BIGINT IDENTITY(1,1)` 作为技术主键。

### 9.2 业务幂等键

对于 normalized 事实表，应设计业务幂等键，常见方式：

```text
business_key_hash = sha256(canonical JSON of stable business key fields)
```

并创建唯一索引；如果对既有表新增幂等键字段，为了避免表中已有历史数据导致 migration 失败，可以先使用 nullable column + filtered unique index，repository 写入时仍强制非空，后续再通过 backfill/alter 收紧。

### 9.3 来源追溯字段

Normalized 表应尽量包含：

```text
source_report_id
source_raw_file_id
source_row_hash
created_at
updated_at
```

如果当前未实现，应在 feature 文档中写入后续优化。

### 9.4 金额和数量

- 金额字段优先使用 `DECIMAL(18, 4)` 或根据业务需要更高精度。
- 费率/转化率字段避免用浮点数，优先 `DECIMAL`。
- 数量字段根据来源语义使用 `INT` 或 `DECIMAL`。

### 9.5 时间

- 数据库记录创建/更新时间使用 UTC：`SYSUTCDATETIME()`。
- 报告业务日期用 `DATE`。
- 源字段如果只有 raw string 且解析规则未稳定，可先保留 `*_raw` 字段，但应在 feature 文档说明。

## 10. 禁止事项

1. 禁止修改已执行的 `001_create_core_tables.sql`、`002_create_indexes.sql`、`003_add_listing_snapshot_business_key_hash.sql`、`004_add_inventory_daily_business_key_hash.sql`、`005_add_sales_traffic_business_key_hashes.sql`、`006_add_settlement_transaction_business_key.sql`、`007_add_order_item_business_key.sql` 和 `008_add_fba_reimbursement_business_key.sql`。
2. 禁止为了让测试通过而让代码和真实数据库 spec 偏移。
3. 禁止在 feature 文档未说明原因时新增表或字段。
4. 禁止把未执行的目标 schema 写进 current schema spec。
5. 禁止直接在业务代码中散落 SQL 写入逻辑，应通过 repository 层。
6. 禁止在 migration 中写入真实密钥或敏感经营数据。

## 11. 当前已知待评估数据库优化

以下不是当前阻塞项，后续如决定实施，应新增 migration：

| 议题 | 当前状态 | 可能 migration |
|---|---|---|
| `amazon_sync_run_log` 记录 inserted/updated 拆分 | CLI 有统计，数据库无字段 | 后续编号，从 010 起 |
| Ads/raw_file_id 关联 | 当前 `schema_validation_event.raw_file_id` 可为 NULL，主要靠 path | 后续结合 raw file registry 设计 |
| Orders business key | Orders 功能设计已完成，表已补充 `source_row_index` / `business_key_hash` | `007_add_order_item_business_key.sql` 已执行，后续如需变化从 `009` 之后的新 migration 开始 |
| FBA Reimbursements business key | FBA Reimbursements 功能设计已完成，表已补充 `source_row_index` / `business_key_hash` | `008_add_fba_reimbursement_business_key.sql` 已执行，后续如需变化从 `009` 之后的新 migration 开始 |

这些优化必须先进入对应 feature 文档，再决定是否写 migration。


## 9. 当前待执行 migration

截至 2026-05-17，以下 migration 已准备但尚未由用户本地执行：

```text
010_add_promotion_coupon_business_keys.sql
011_add_inventory_ledger_business_keys.sql
```

执行后必须运行：

```powershell
python scripts/export_database_schema_spec.py --output-prefix after_010_promotion_coupon_business_keys --include-row-counts
python scripts/export_database_schema_spec.py --output-prefix after_011_inventory_ledger_business_keys --include-row-counts
```

并据 live schema 更新 `docs/database/database_current_schema_spec.md`。

## 9. 012 Job Config Migration Status

当前已准备但尚未执行：

```text
sql/migrations/012_create_ingestion_job_config.sql
sql/seeds/001_seed_ingestion_job_config_core_jobs.sql
```

用途：新增 `pipeline_job_config` 表，用于记录手动和未来自动化任务的执行周期、默认回看窗口、脚本路径和执行阶段。

执行顺序：

```powershell
python scripts/run_sql_migration.py --file sql/migrations/012_create_ingestion_job_config.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/012_create_ingestion_job_config.sql
python scripts/run_sql_migration.py --file sql/seeds/001_seed_ingestion_job_config_core_jobs.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/seeds/001_seed_ingestion_job_config_core_jobs.sql
python scripts/export_database_schema_spec.py --output-prefix after_012_job_config --include-row-counts
```

执行成功后，必须更新：

```text
docs/database/database_current_schema_spec.md
docs/operations/ingestion_job_cadence_catalog.md
docs/project/progress_next_steps.md
```
