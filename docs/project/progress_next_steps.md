# SellerDataPipeline 当前进展与下一步计划

> 更新时间：2026-05-17  
> 当前版本：v1.49 core ingestion implemented; action lint fixed  
> 文档定位：记录项目真实进展、已完成里程碑、当前非阻塞问题和下一步开发顺序。本文档只记录真实状态和近期计划，不承载详细功能设计。

## 1. 当前一句话状态

项目已经完成核心 SP-API / Ads normalized ingestion 底座，并进入 **运营补充数据收尾阶段**。当前已完成并通过真实 Azure SQL execute + 第二次 execute 幂等性验证的链路包括：

```text
Amazon Ads SP reports -> 4 张 Ads daily 表
GET_MERCHANT_LISTINGS_ALL_DATA -> amazon_listing_snapshot
GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA -> amazon_inventory_daily
GET_SALES_AND_TRAFFIC_REPORT -> amazon_sales_traffic_daily / amazon_sales_traffic_asin_daily
GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2 -> amazon_settlement_transaction
GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL -> amazon_order_item
GET_FBA_REIMBURSEMENTS_DATA -> amazon_fba_reimbursement
GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA -> amazon_fba_fee_preview
GET_PROMOTION_PERFORMANCE_REPORT / GET_COUPON_PERFORMANCE_REPORT -> 4 张 promotion/coupon 表
```

最新 Promotion/Coupon 验收结果：

```text
Dry-run: prepared_rows=10 requires_review=False
首次 execute: sync_run_id=17, attempted=10 inserted=10 updated=0 written=10 skipped=0
第二次 execute: sync_run_id=18, attempted=10 inserted=0 updated=10 written=10 skipped=0
```

当前基础设施状态：

```text
001/002/003/004/005/006/007/008/009/010/011 migration 已执行成功
FBA Fee Preview 专用 ingestion 已完成 execute/幂等验证：sync_run_id=15 inserted=8；sync_run_id=16 updated=8
Promotion/Coupon 专用 ingestion 已完成 execute/幂等验证：sync_run_id=17 inserted=10；sync_run_id=18 updated=10
Inventory Ledger 专用 ingestion 已完成 execute/幂等验证：sync_run_id=19 inserted=357；sync_run_id=20 updated=357
Azure SQL connection warm-up retry 已启用，默认 max_attempts=6
scripts/export_database_schema_spec.py 已可导出 live schema snapshot
```

下一条主线切换到利润核算设计：

```text
feature_profit_calculation.md
  -> 定义利润核算口径
  -> 设计 SKU 成本 / 头程海运成本 / 广告费 / 促销折扣 / 退款赔偿等归因规则
  -> 再决定是否需要新的 fact 表、视图或报表输出表
```

最新 Inventory Ledger 验收结果：

```text
Dry-run: prepared_rows=357 requires_review=False
首次 execute: sync_run_id=19, attempted=357 inserted=357 updated=0 written=357 skipped=0
第二次 execute: sync_run_id=20, attempted=357 inserted=0 updated=357 written=357 skipped=0
```

## 2. 已完成里程碑


### 2.1 SP-API 基础连接

已实现并验证：

```text
python scripts/test_sp_api_connection.py
```

目标是验证本地 `.env` 中的 SP-API refresh token、LWA token exchange 和基础 endpoint 访问。

### 2.2 SP-API Reports 本地取样

已完成多类 SP-API report 的本地下载与字段分析，脱敏字段样例位于：

```text
requirements/data_samples/
```

这些样例后续会迁移/整理到 `docs/data_access/`，形成正式数据接入目录。

已取样的主要数据方向包括：

- Listing
- FBA 库存
- 销售与流量
- Settlement 结算
- 订单
- FBA 赔偿
- FBA fee preview
- 库存流水
- 预留库存
- 库存规划/补货
- Promotion
- Coupon

### 2.3 Amazon Ads 取样与入库

已完成 Amazon Ads profile 发现、Sponsored Products 多类报表下载、schema guard、dry-run preview、真实入库与幂等验证。

已验证 Ads report 类型：

```text
spCampaigns
spTargeting
spSearchTerm
spAdvertisedProduct
```

`spPurchasedProduct` 已在取样计划中，但本轮尚未纳入真实入库表。

### 2.4 Azure SQL 建表与索引

已在 Azure SQL `amazon_ops` 执行：

```text
python scripts/run_sql_migration.py --file sql/migrations/001_create_core_tables.sql
-> executed_batches=29/29

python scripts/run_sql_migration.py --file sql/migrations/002_create_indexes.sql
-> executed_batches=54/54
```

执行后检查结果：

```text
Database: amazon_ops
Server: amazon-ops-sql
Edition: SQL Azure
User tables: 28
```

当前真实数据库结构记录在：

```text
docs/database/database_current_schema_spec.md
```

重要维护规则：`001_create_core_tables.sql`、`002_create_indexes.sql`、`003_add_listing_snapshot_business_key_hash.sql`、`004_add_inventory_daily_business_key_hash.sql`、`005_add_sales_traffic_business_key_hashes.sql`、`006_add_settlement_transaction_business_key.sql`、`007_add_order_item_business_key.sql` 和 `008_add_fba_reimbursement_business_key.sql` 已经执行成功，后续不允许修改这些历史 migration。

### 2.5 Amazon Ads 真实入库

首次真实写库命令：

```text
python scripts/ingest_ads_reports.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER --execute
```

首次入库结果：

```text
sync_run_id=1
prepared_rows=200
requires_review=False
upsert attempted=200 inserted=200 updated=0 written=200 skipped=0

amazon_ads_sp_campaign_daily: attempted=8 inserted=8 updated=0 skipped=0
amazon_ads_sp_targeting_daily: attempted=99 inserted=99 updated=0 skipped=0
amazon_ads_sp_search_term_daily: attempted=61 inserted=61 updated=0 skipped=0
amazon_ads_sp_advertised_product_daily: attempted=32 inserted=32 updated=0 skipped=0
```

第二次重复执行同一批数据，幂等性验证通过：

```text
sync_run_id=2
upsert attempted=200 inserted=0 updated=200 written=200 skipped=0

amazon_ads_sp_campaign_daily: attempted=8 inserted=0 updated=8 skipped=0
amazon_ads_sp_targeting_daily: attempted=99 inserted=0 updated=99 skipped=0
amazon_ads_sp_search_term_daily: attempted=61 inserted=0 updated=61 skipped=0
amazon_ads_sp_advertised_product_daily: attempted=32 inserted=0 updated=32 skipped=0
```

当前四张 Ads 表行数：

```text
amazon_ads_sp_campaign_daily              8
amazon_ads_sp_targeting_daily             99
amazon_ads_sp_search_term_daily           61
amazon_ads_sp_advertised_product_daily    32
```

`amazon_schema_validation_event` 已记录 Ads report 的 ok 事件：

```text
validation_status = ok
severity = info
requires_review = False
message = Observed report fields match the expected schema.
```

### 2.6 数据库检查脚本

已新增：

```text
scripts/check_database_status.py
```

用途：一次性输出 Azure SQL 连接诊断、重点表行数、最新 sync run、最新 schema validation event。

常用命令：

```powershell
python scripts/check_database_status.py
python scripts/check_database_status.py --json
python scripts/check_database_status.py --all-tables
python scripts/check_database_status.py --table amazon_ads_sp_campaign_daily --table amazon_sync_run_log
```

注意：`amazon_sync_run_log` 当前字段是：

```text
rows_read
rows_written
rows_skipped
rows_failed
```

不是：

```text
records_attempted
records_inserted
records_updated
records_skipped
```


### 2.7 Azure SQL connection warm-up retry

已新增 Azure SQL 连接预热和重试能力。背景是 Azure SQL serverless 长时间空闲后可能处于自动暂停/恢复过程中，第一次 `pyodbc.connect()` 可能返回类似：

```text
08001 Login timeout expired
Unable to complete login process due to delay in login response
```

当前处理方式：

```text
get_connection()
  -> pyodbc.connect retry for known transient connection errors
  -> SELECT 1 warm-up check
  -> only then yield connection to migration / ingestion business SQL
```

已新增配置：

```env
AZURE_SQL_CONNECT_MAX_ATTEMPTS='6'
AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS='5'
AZURE_SQL_CONNECT_RETRY_BACKOFF='1.8'
```

也可对连接测试命令临时覆盖：

```powershell
python scripts/test_azure_sql_connection.py --json --max-attempts 8 --retry-delay-seconds 8
```

### 2.7.1 Azure SQL firewall/IP allowlist 观察

2026-05-17 运行 `scripts/export_database_schema_spec.py` 时，前两次连接出现 serverless resume 类 timeout，随后返回 `40615` / 当前客户端 IP 未被 Azure SQL Server firewall 放行。该场景已经确认不是 warm-up retry 能解决的问题。

处理策略已固化：

```text
08001 / timeout / delay in login response
  -> 连接层 retry + SELECT 1 warm-up

40615 / client IP not allowed
  -> fail fast，提示放行当前公网 IP 或配置云端稳定出站网络
```

相关文档：`docs/database/azure_sql_connection_runbook.md` 与 `docs/adr/ADR-006-azure-sql-connection-warmup.md`。

### 2.7.2 Schema export identity column compatibility fix

2026-05-17 用户放行 firewall 后，`scripts/export_database_schema_spec.py --include-row-counts` 连接预热已在第 3 次尝试成功，但随后读取 `sys.identity_columns.seed_value / increment_value` 时触发 pyodbc 错误：

```text
ODBC SQL type -150 is not yet supported
```

根因：SQL Server 的 `sys.identity_columns.seed_value` 和 `increment_value` 是 `sql_variant` 类型，部分 pyodbc / ODBC Driver 组合无法直接 fetch。

处理：schema export 的 columns catalog 查询已改为：

```sql
CONVERT(nvarchar(100), ic.seed_value) AS identity_seed,
CONVERT(nvarchar(100), ic.increment_value) AS identity_increment
```

并新增 `AzureSqlSchemaExportError`，后续如果 schema export catalog 查询失败，CLI 会输出带 query context 的友好错误，而不是直接甩完整 traceback。

### 2.8 SP-API Listing 入库代码准备

已新增 Listing 快照入库的第一版代码闭环：

```text
src/seller_data_pipeline/ingestion/listing_table_mapping.py
src/seller_data_pipeline/ingestion/listing_ingestion_dry_run.py
src/seller_data_pipeline/ingestion/listing_ingestion.py
src/seller_data_pipeline/db/repositories/listing_repo.py
scripts/ingest_listing_snapshot.py
```

已使用当前真实 raw file 完成本地 dry-run 和 Azure SQL execute 验证：

```text
python scripts/ingest_listing_snapshot.py --marketplace-id ATVPDKIKX0DER
-> prepared_rows=6 requires_review=False

python scripts/ingest_listing_snapshot.py --marketplace-id ATVPDKIKX0DER --execute
-> sync_run_id=3, attempted=6 inserted=6 updated=0 written=6 skipped=0

python scripts/ingest_listing_snapshot.py --marketplace-id ATVPDKIKX0DER --execute
-> sync_run_id=4, attempted=6 inserted=0 updated=6 written=6 skipped=0
```

已新增单元测试并通过：

```text
PYTHONPATH=src pytest -q
-> 118 passed
python -m compileall -q scripts src tests
-> passed
```

当前环境没有安装 `ruff`，因此本轮未能在沙盒内执行 `ruff check`；用户本地覆盖后应执行：

```powershell
ruff check src tests scripts
ruff format src tests scripts
```


### 2.9 SP-API Inventory 入库验收

Inventory normalized ingestion 已完成开发和用户本地 Azure SQL 验证，当前功能状态为 `Implemented`：

```text
GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA -> amazon_inventory_daily
004_add_inventory_daily_business_key_hash.sql -> executed, 3/3 batches
dry-run: prepared_rows=5, requires_review=False
first execute: sync_run_id=5, inserted=5, updated=0
second execute: sync_run_id=6, inserted=0, updated=5
```

当前 `amazon_inventory_daily` 已验证业务幂等键有效，第二次执行未重复插入。后续如果源字段变化，应先更新 `docs/features/feature_inventory_ingestion.md`，必要时新增 migration，不得回改 `001/002/003/004`。

### 2.10 Orders 007 migration 与 dry-run 开发

已准备：

```text
sql/migrations/007_add_order_item_business_key.sql
-> local dry-run parse: 4 executable batches
```

该 migration 计划给 `dbo.amazon_order_item` 增加：

```text
source_row_index INT NULL
business_key_hash NVARCHAR(100) NULL
UX_amazon_order_item_business_key_hash filtered unique index
```

尚未在 Azure SQL 执行，因此 `database_current_schema_spec.md` 不把这些字段写成当前真实字段。


## 3. 文档体系更新进展

正式文档已从 `requirements/` 迁移到 `docs/` 并开始按最终架构拆分。

### 3.1 第一批：文档骨架与治理规则

已新增/更新：

```text
README.md
docs/README.md
docs/project/project_overview.md
docs/project/development_rules.md
docs/project/progress_next_steps.md
docs/features/FEATURE_TEMPLATE.md
docs/database/database_migration_policy.md
docs/database/database_current_schema_spec.md
docs/adr/ADR-001-documentation-structure.md
docs/adr/ADR-002-do-not-edit-executed-migrations.md
```

### 3.2 第二批：数据接入目录

已新增/更新：

```text
docs/data_access/README.md
docs/data_access/amazon_data_access_catalog.md
docs/data_access/sp_api_reports_catalog.md
docs/data_access/amazon_ads_reports_catalog.md
docs/data_access/seller_central_manual_exports.md
```

### 3.3 第三批：已实现功能文档

已新增/更新：

```text
docs/features/README.md
docs/features/feature_azure_sql_foundation.md
docs/features/feature_ads_ingestion.md
```

### 3.4 第四批：Listing 入库功能设计

已新增/更新：

```text
docs/features/feature_listing_snapshot_ingestion.md
README.md
docs/README.md
docs/features/README.md
```

第四批只做功能设计，当时不改代码、不改 SQL migration。文档中已明确：`amazon_listing_snapshot` 真实表已存在，但为了严谨幂等，应在代码开发前新增独立 migration 补 `business_key_hash` 和唯一索引；该 migration 已在第五批准备完成，执行成功后再更新 current schema spec。

当前文档策略：

```text
docs/ 是正式文档目录。
requirements/ 中历史文档暂时作为迁移来源和兼容参考。
后续新设计、新功能、新进度应优先维护 docs/。
```


### 3.5 第五批：Listing 003 migration 准备与执行

已新增：

```text
sql/migrations/003_add_listing_snapshot_business_key_hash.sql
```

本批准备 migration 后，用户已在 Azure SQL `amazon_ops` 上完成 dry-run 和正式执行。003 的目的：为 `dbo.amazon_listing_snapshot` 增加稳定的 `business_key_hash` 幂等键，并创建唯一过滤索引 `UX_amazon_listing_snapshot_business_key_hash`。

重要状态：

```text
003 migration = executed, 3/3 batches
```

当前 `docs/database/database_current_schema_spec.md` 已把 `business_key_hash` 字段和 `UX_amazon_listing_snapshot_business_key_hash` 索引记录为真实库结构。

### 3.6 第六批：迭代工作流 SOP 与治理 ADR

已新增/更新：

```text
docs/project/iteration_workflow.md
docs/adr/ADR-003-feature-doc-before-implementation.md
docs/adr/ADR-004-database-spec-from-live-schema.md
```

本批明确了后续 AI / 开发者的标准迭代流程：

```text
新需求分类
-> 读取相关 docs
-> 更新 data_access 或 feature 设计文档
-> 判断是否需要数据库变更
-> 新增 migration
-> dry-run / execute
-> 查询真实 Azure SQL schema
-> 更新 database_current_schema_spec.md
-> 开发代码
-> dry-run / execute / 幂等性 / 测试验收
-> 更新 progress 与相关文档
```

特别明确：`database_current_schema_spec.md` 必须来自真实 Azure SQL schema 查询结果，不能只根据 migration 文件推断。

## 4. 当前非阻塞问题 / 后续优化点

### 4.1 sync_run_log 暂无 inserted/updated 拆分

CLI 输出目前能看到：

```text
inserted=0 updated=200
```

但数据库审计表只有：

```text
rows_read / rows_written / rows_skipped / rows_failed
```

是否新增 `rows_inserted` / `rows_updated` 可以等 SP-API repository 前再决定。当前不阻塞。

如需要补强，应该新增 migration，例如：

```text
008_add_sync_run_upsert_counts.sql 或后续编号
```

### 4.2 Ads schema_validation_event.raw_file_id 仍为 NULL

当前 Ads 入库有 `raw_file_path`，但 `raw_file_id` 尚未关联到 `amazon_raw_report_file`。

后续建议补强：

```text
raw file 先登记 amazon_raw_report_file
  -> schema_validation_event.raw_file_id 关联 raw file
  -> normalized 表 source_raw_file_id 关联 raw file
```

这会让审计追溯更稳定。

### 4.3 requirements 历史文档尚未全部迁移

`requirements/database_design.md` 仍包含上一版整合设计内容。数据接入部分已经拆入 `docs/data_access/`，已实现功能部分已经开始拆入 `docs/features/`。后续还需要继续把待开发功能拆成独立 feature 文档，例如 Orders、Profit、Weekly Report、Clearance Decision Support。Listing、Inventory、Sales & Traffic、Settlement 入库功能已经完成当前阶段设计与实现。

迁移完成前，避免同时维护两套详细设计。新的设计应优先进入 `docs/`，旧 `requirements/` 文档只作为迁移来源和历史参考。

## 5. 下一步开发顺序

建议按以下顺序继续，不要先上 Azure Container Apps Jobs：

### 5.1 文档第二批：数据接入目录

已完成。正式数据接入目录位于：

```text
docs/data_access/README.md
docs/data_access/amazon_data_access_catalog.md
docs/data_access/sp_api_reports_catalog.md
docs/data_access/amazon_ads_reports_catalog.md
docs/data_access/seller_central_manual_exports.md
```

这一批只写数据来源、接口、文件格式、字段结构、取样状态，不写业务功能。

### 5.2 文档第三批：已实现功能文档

已完成。已跑通能力已经沉淀为功能文档样板：

```text
docs/features/README.md
docs/features/feature_azure_sql_foundation.md
docs/features/feature_ads_ingestion.md
```

### 5.3 文档第四批：Listing 功能设计

已完成第一版：

```text
docs/features/feature_listing_snapshot_ingestion.md
```

该文档明确了 Listing 入库的业务目标、范围、字段映射、schema guard、幂等键、migration 需求、CLI 建议、测试计划和验收标准。

### 5.4 已完成：Listing normalized ingestion

Listing normalized ingestion 已完成开发和用户本地 Azure SQL 验证。当前功能状态为 `Implemented`：

```text
GET_MERCHANT_LISTINGS_ALL_DATA -> amazon_listing_snapshot
dry-run: prepared_rows=6, requires_review=False
first execute: sync_run_id=3, inserted=6, updated=0
second execute: sync_run_id=4, inserted=0, updated=6
```

后续如果 Listing 源字段出现变化，应按 schema guard 结果更新 `docs/features/feature_listing_snapshot_ingestion.md`，必要时新增 migration，不要回改 `001/002/003`。

### 5.5 已完成：Inventory normalized ingestion

Inventory normalized ingestion 已完成开发和用户本地 Azure SQL 验证。当前功能状态为 `Implemented`：

```text
GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA -> amazon_inventory_daily
dry-run: prepared_rows=5, requires_review=False
first execute: sync_run_id=5, inserted=5, updated=0
second execute: sync_run_id=6, inserted=0, updated=5
```

后续如果 Inventory 源字段出现变化，应按 schema guard 结果更新 `docs/features/feature_inventory_ingestion.md`，必要时新增 migration，不要回改 `001/002/003/004`。

### 5.6 已完成：Sales & Traffic normalized ingestion

当前链路已经完成：

```text
GET_SALES_AND_TRAFFIC_REPORT
  -> amazon_sales_traffic_daily
  -> amazon_sales_traffic_asin_daily
```

验收结果：

```text
Dry-run: prepared_rows=7 requires_review=False
首次 execute: sync_run_id=7, attempted=7 inserted=7 updated=0 written=7 skipped=0
  amazon_sales_traffic_daily: attempted=6 inserted=6 updated=0 skipped=0
  amazon_sales_traffic_asin_daily: attempted=1 inserted=1 updated=0 skipped=0
第二次 execute: sync_run_id=8, attempted=7 inserted=0 updated=7 written=7 skipped=0
  amazon_sales_traffic_daily: attempted=6 inserted=0 updated=6 skipped=0
  amazon_sales_traffic_asin_daily: attempted=1 inserted=0 updated=1 skipped=0
```

### 5.7 已完成：Settlement normalized ingestion

当前链路已经完成：

```text
GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2
  -> amazon_settlement_transaction
```

验收结果：

```text
Dry-run: prepared_rows=4911 processed_files=8 skipped_files=0 requires_review=False
首次 execute: sync_run_id=9, attempted=4911 inserted=4911 updated=0 written=4911 skipped=0
第二次 execute: sync_run_id=10, attempted=4911 inserted=0 updated=4911 written=4911 skipped=0
```

Settlement 是利润核算的核心财务入账事实表。首版 ingestion 只负责保存逐行结算明细和保守分类，不直接生成最终会计利润结论。

### 5.8 已完成：Orders normalized ingestion

已完成链路：

```text
GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL
  -> amazon_order_item
```

当前状态：

1. Orders 样例已存在：1 份 raw file，112 行，33 个源字段。
2. `007_add_order_item_business_key.sql` 已执行并导出 `after_007_order_item_business_key` live schema。
3. 专用 parser / schema guard / dry-run / repository / CLI 已开发完成。
4. 用户本地已完成 dry-run、首次 execute 和第二次 execute 幂等性验证。

验收证据：

```text
Dry-run: prepared_rows=112 requires_review=False
首次 execute: sync_run_id=11 inserted=112 updated=0
第二次 execute: sync_run_id=12 inserted=0 updated=112
```

注意：Orders 是订单行项目事实表，用于订单/SKU 维度分析和对账。它不是最终利润口径，利润计算仍以后续 Settlement、Ads、SKU cost、FBA fee、Reimbursements 等综合模型为准。

### 5.9 已完成：FBA Reimbursements normalized ingestion

已完成链路：

```text
GET_FBA_REIMBURSEMENTS_DATA
  -> amazon_fba_reimbursement
```

验收结果：

```text
Dry-run: prepared_rows=19 requires_review=False
首次 execute: sync_run_id=13 attempted=19 inserted=19 updated=0 written=19 skipped=0
第二次 execute: sync_run_id=14 attempted=19 inserted=0 updated=19 written=19 skipped=0
```

状态说明：

1. `008_add_fba_reimbursement_business_key.sql` 已 dry-run、execute 成功，并导出 `after_008_fba_reimbursement_business_key` live schema。
2. `database_current_schema_spec.md` 已记录 `source_row_index`、`business_key_hash` 和 `UX_amazon_fba_reimbursement_business_key_hash`。
3. 专用 parser / schema guard / dry-run / repository / CLI 已开发完成。
4. 真实 Azure SQL execute 与第二次 execute 幂等性验证均已完成。
5. `feature_fba_reimbursements_ingestion.md` 已更新为 `Implemented`。

### 5.10 当前主线：FBA Fee Preview ingestion

下一条主线切换到：

```text
GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA
  -> amazon_fba_fee_preview
```

当前状态：

1. FBA Fee Preview 样例已存在：1 份 raw file，8 行，31 个源字段。
2. 目标表 `amazon_fba_fee_preview` 已由 `001_create_core_tables.sql` 创建。
3. Parser 已存在：`src/seller_data_pipeline/parsers/amazon/fba_estimated_fees_parser.py`。
4. 功能设计文档已建立：`docs/features/feature_fba_fee_preview_ingestion.md`。
5. `009_add_fba_fee_preview_business_key.sql` 已执行成功，`database_current_schema_spec.md` 已同步 live schema。
6. 专用 ingestion 已开发完成并通过 dry-run：prepared_rows=8 requires_review=False。

下一步：

```text
1. 用户本地执行 python scripts/ingest_fba_fee_preview_report.py --marketplace-id ATVPDKIKX0DER --execute
2. 重复执行同一命令验证幂等性
3. 预期首次 inserted=8 updated=0，第二次 inserted=0 updated=8
4. 通过后将 FBA Fee Preview 更新为 Implemented
5. 开始利润核算功能设计
```
