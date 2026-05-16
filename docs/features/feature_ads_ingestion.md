# Feature: Amazon Ads Sponsored Products 报表入库

> 文档状态：正式功能文档  
> 负责人：AI assisted / Zifei 复核  
> 更新时间：2026-05-16  
> 功能状态：Implemented  
> 相关数据接入文档：`docs/data_access/amazon_ads_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关基础设施功能：`docs/features/feature_azure_sql_foundation.md`

---

## 1. 功能摘要

本功能负责把 Amazon Ads Reporting v3 中 Sponsored Products 的日维度 raw JSON 报表转换为 Azure SQL normalized 表。当前已实现四类报表：`spCampaigns`、`spTargeting`、`spSearchTerm`、`spAdvertisedProduct`。

功能链路包括：读取本地最新 raw JSON、schema guard、parser、字段映射、dry-run preview、Azure SQL `MERGE`/upsert、sync run log、schema validation event 和幂等性验证。当前已完成真实入库：首次 inserted=200，第二次重复执行 inserted=0、updated=200，目标表总行数保持 200。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 数据源取样 | 已完成 |
| Parser | 已完成 |
| Dry-run preview | 已完成 |
| Schema guard | 已完成 |
| Repository/upsert | 已完成 |
| Azure SQL execute | 已验证 |
| 幂等性验证 | 已通过 |
| 单元测试 | 已完成 |
| 文档同步 | 已完成本功能文档第一版 |

功能整体状态：`Implemented`。

## 3. 业务目标

本功能服务于广告优化和经营复盘，是后续运营分析的第一条真实入库闭环。

它帮助解决的问题：

1. **广告花费可见**：沉淀每日 impressions、clicks、cost、sales、purchases、units sold。
2. **Campaign 层复盘**：识别哪些 campaign 有花费、有曝光、是否带来销售。
3. **Targeting / keyword 层优化**：为后续加词、否词、调 bid、暂停低效词提供数据基础。
4. **Search term 层洞察**：识别用户真实搜索词，辅助优化关键词和 listing 文案。
5. **SKU/ASIN 层广告贡献**：结合 advertised product 数据判断广告流量打到哪些 SKU/ASIN。
6. **后续利润核算输入**：广告 cost 可用于运营分析；财务入账口径仍应优先使用 settlement 中的广告扣费。

当前公司体量较小，广告数据入库优先级高，因为它能快速支撑清仓、控制广告浪费、Prime Day 前后促销复盘等运营动作。

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 Amazon Ads raw JSON 文件。
- 支持四类 Sponsored Products report：
  - `spCampaigns`
  - `spTargeting`
  - `spSearchTerm`
  - `spAdvertisedProduct`
- 使用 sampling plan 中的 expected schema 做 schema guard。
- 生成 DB-ready preview JSONL 文件。
- 使用 `business_key_hash` 对四张 Ads 表执行 Azure SQL `MERGE`/upsert。
- 写入 `amazon_sync_run_log`。
- 写入 `amazon_schema_validation_event`。
- 支持 dry-run 默认模式和 `--execute` 真实写库模式。
- 支持重复执行幂等性。

### 4.2 本功能不包含

- 不负责提交和下载 Ads report request；下载属于 Ads data access / sampling 服务。
- 不负责 Sponsored Brands 或 Sponsored Display。
- 不负责 `spPurchasedProduct` 入库；当前样例为空，且目标表尚未创建。
- 不负责广告优化策略生成，例如自动否词、自动调 bid。
- 不负责财务入账级广告费确认；财务口径以后应结合 settlement。
- 不负责 Azure Container Apps Jobs 定时运行；当前只验证本地 CLI。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| Amazon Ads API | `spCampaigns` | JSON top-level array | 已取样，8 行 | 已解析并入库 | Campaign-level daily metrics。 |
| Amazon Ads API | `spTargeting` | JSON top-level array | 已取样，99 行 | 已解析并入库 | Keyword/targeting-level daily metrics。 |
| Amazon Ads API | `spSearchTerm` | JSON top-level array | 已取样，61 行 | 已解析并入库 | Shopper search-term daily metrics。 |
| Amazon Ads API | `spAdvertisedProduct` | JSON top-level array | 已取样，32 行 | 已解析并入库 | Advertised SKU/ASIN daily metrics。 |
| Amazon Ads API | `spPurchasedProduct` | JSON top-level array | 已取样，0 行 | 未入库 | 当前为空样例；不在本功能当前范围。 |

当前 raw 路径约定：

```text
reports/raw/amazon_ads/{profile_id}/{report_type_id}/{date}/{ads_report_id}.json
```

当前已验证参数：

| 参数 | 当前值 |
|---|---|
| US Ads profile | `3917953989967300` |
| US marketplace | `ATVPDKIKX0DER` |
| source_system | `amazon_ads` |

## 6. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/amazon_ads/{profile_id}/{timestamp}/ads_ingestion_summary.json` | 本次 dry-run / execute 汇总。 |
| Task audit event | `runtime/ingestion/amazon_ads/{profile_id}/{timestamp}/task_audit_event.json` | 本地任务审计快照。 |
| Schema events JSONL | `runtime/ingestion/amazon_ads/{profile_id}/{timestamp}/schema_validation_events.jsonl` | 入库前字段验证结果。 |
| Preview rows | `runtime/ingestion/amazon_ads/{profile_id}/{timestamp}/previews/*.preview.jsonl` | DB-ready preview，不加 `--execute` 时只生成这些文件。 |
| Azure SQL table | `dbo.amazon_ads_sp_campaign_daily` | Campaign 日维度广告表现。 |
| Azure SQL table | `dbo.amazon_ads_sp_targeting_daily` | Targeting / keyword 日维度广告表现。 |
| Azure SQL table | `dbo.amazon_ads_sp_search_term_daily` | Search term 日维度广告表现。 |
| Azure SQL table | `dbo.amazon_ads_sp_advertised_product_daily` | Advertised SKU/ASIN 日维度广告表现。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录每类 report 的 schema guard 结果。 |

## 7. 处理流程

```text
local raw Ads JSON
  -> find latest raw file per reportTypeId
  -> analyze observed fields
  -> compare with expected schema from Ads sampling plan
  -> if requires_review=True: block database write
  -> parse raw JSON rows into AdsReportRecord
  -> map records to target-table DB rows
  -> write preview JSONL
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE preview rows into allowlisted Ads tables by business_key_hash
  -> insert schema validation events
  -> update amazon_sync_run_log final status
  -> commit transaction
```

关键行为：

1. 默认模式是 dry-run，不写数据库。
2. 只有显式传入 `--execute` 才会连接 Azure SQL 并写库。
3. 如果 schema guard 产生 `requires_review=True`，真实写库会被阻断。
4. 写库时先创建 running 状态的 sync run，再 upsert，最后更新 success/failed。
5. 如果 upsert 阶段异常，会尝试 rollback 并写失败审计。

## 8. 字段映射

### 8.1 源字段到标准字段

| 源字段 | 标准字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|---|
| `date` | `report_date` | date string | yes | Ads report 日维度日期；写入 SQL `DATE`。 |
| `campaignId` | `campaign_id` | string id | report-dependent | Campaign ID。 |
| `campaignName` | `campaign_name` | string | no | Campaign 名称。 |
| `campaignStatus` | `campaign_status` | string | `spCampaigns` | Campaign 状态。 |
| `adGroupId` | `ad_group_id` | string id | report-dependent | Ad group ID。 |
| `adGroupName` | `ad_group_name` | string | report-dependent | Ad group 名称。 |
| `keywordId` | `keyword_id` | string id | report-dependent | Keyword ID；targeting/search-term 表使用。 |
| `keyword` | `keyword` | string | report-dependent | Keyword 文本。 |
| `matchType` | `match_type` | string | report-dependent | 匹配类型。 |
| `targeting` | `targeting` | string | report-dependent | Targeting 表达式。 |
| `searchTerm` | `search_term` | string | `spSearchTerm` | 用户真实搜索词。 |
| `advertisedAsin` | `advertised_asin` | string | `spAdvertisedProduct` | 被广告投放的 ASIN。 |
| `advertisedSku` | `advertised_sku` | string | `spAdvertisedProduct` | 被广告投放的 seller SKU。 |
| `purchasedAsin` | `purchased_asin` | string | `spPurchasedProduct` only | 当前不入库。 |
| `impressions` | `impressions` | int | no | 曝光。 |
| `clicks` | `clicks` | int | no | 点击。 |
| `cost` | `cost` | decimal | no | 广告花费；Ads 运营口径。 |
| `sales7d` | `sales_7d` | decimal | no | 7 天归因销售额。 |
| `purchases7d` | `purchases_7d` | int | no | 7 天归因购买次数。 |
| `unitsSoldClicks7d` | `units_sold_clicks_7d` | int | no | 7 天点击归因售出件数。 |
| raw row object | `raw_data` | JSON string | yes | 完整保留源行，便于后续补字段。 |

解析规则：

- ID 类字段统一按 string 保存，避免大整数精度问题。
- 空字符串和 null 统一转为 `None`。
- 整数字段使用 `Decimal(value)` 后转 int。
- 金额字段使用 `Decimal`，写 preview 时转为 JSON-safe 字符串，写 SQL 时进入 `DECIMAL(18,4)`。
- `raw_data` 使用 deterministic JSON 字符串保留。

### 8.2 标准字段到数据库字段

| 标准字段 | 目标表 | 目标字段 | 类型 | 转换规则 |
|---|---|---|---|---|
| `profile_id` | 四张 Ads 日表 | `profile_id` | `NVARCHAR(100)` | CLI 参数或 `.env`。 |
| `marketplace_id` | 四张 Ads 日表 | `marketplace_id` | `NVARCHAR(50)` | CLI 参数或 `.env`。 |
| `report_date` | 四张 Ads 日表 | `report_date` | `DATE` | 来自 `date`。 |
| `campaign_id` | campaign/targeting/search-term/advertised-product | `campaign_id` | `NVARCHAR(100)` | 来自 `campaignId`。 |
| `campaign_name` | campaign/targeting/search-term/advertised-product | `campaign_name` | `NVARCHAR(500)` | 来自 `campaignName`。 |
| `campaign_status` | campaign | `campaign_status` | `NVARCHAR(100)` | 来自 `campaignStatus`。 |
| `ad_group_id` | targeting/search-term/advertised-product | `ad_group_id` | `NVARCHAR(100)` | 来自 `adGroupId`。 |
| `ad_group_name` | targeting/search-term/advertised-product | `ad_group_name` | `NVARCHAR(500)` | 来自 `adGroupName`。 |
| `keyword_id` | targeting/search-term | `keyword_id` | `NVARCHAR(100)` | 来自 `keywordId`。 |
| `keyword` | targeting/search-term | `keyword` | `NVARCHAR(500)` | 来自 `keyword`。 |
| `match_type` | targeting/search-term | `match_type` | `NVARCHAR(100)` | 来自 `matchType`。 |
| `targeting` | targeting/search-term | `targeting` | `NVARCHAR(1000)` | 来自 `targeting`。 |
| `search_term` | search-term | `search_term` | `NVARCHAR(1000)` | 来自 `searchTerm`。 |
| `advertised_asin` | advertised-product | `advertised_asin` | `NVARCHAR(50)` | 来自 `advertisedAsin`。 |
| `advertised_sku` | advertised-product | `advertised_sku` | `NVARCHAR(200)` | 来自 `advertisedSku`。 |
| `impressions` | 四张 Ads 日表 | `impressions` | `INT` | 来自 `impressions`。 |
| `clicks` | 四张 Ads 日表 | `clicks` | `INT` | 来自 `clicks`。 |
| `cost` | 四张 Ads 日表 | `cost` | `DECIMAL(18,4)` | 来自 `cost`。 |
| `sales_7d` | 四张 Ads 日表 | `sales_7d` | `DECIMAL(18,4)` | 来自 `sales7d`。 |
| `purchases_7d` | 四张 Ads 日表 | `purchases_7d` | `INT` | 来自 `purchases7d`。 |
| `units_sold_clicks_7d` | 四张 Ads 日表 | `units_sold_clicks_7d` | `INT` | 来自 `unitsSoldClicks7d`。 |
| `source_*` | 四张 Ads 日表 | `source_*` | mixed | 由 parser / ingestion 填充。 |
| `business_key_hash` | 四张 Ads 日表 | `business_key_hash` | `NVARCHAR(100)` | SHA256 canonical business key。 |
| `raw_data` | 四张 Ads 日表 | `raw_data` | `NVARCHAR(MAX)` | 完整源行 JSON。 |

## 9. 目标数据表设计

### 9.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.amazon_ads_sp_campaign_daily` | yes | Campaign 日维度广告表现 | MERGE/upsert |
| `dbo.amazon_ads_sp_targeting_daily` | yes | Targeting / keyword 日维度广告表现 | MERGE/upsert |
| `dbo.amazon_ads_sp_search_term_daily` | yes | Search term 日维度广告表现 | MERGE/upsert |
| `dbo.amazon_ads_sp_advertised_product_daily` | yes | Advertised SKU/ASIN 日维度广告表现 | MERGE/upsert |
| `dbo.amazon_sync_run_log` | yes | 任务审计 | insert then update |
| `dbo.amazon_schema_validation_event` | yes | schema guard 审计 | append-only insert |
| `dbo.amazon_raw_report_file` | yes | raw file registry | 当前本功能尚未写入 |

注意：`dbo.amazon_ads_sp_purchased_product_daily` 当前不存在，`spPurchasedProduct` 在 table mapping 中 `table_ready=False`，不应被当作已实现入库能力。

### 9.2 业务主键 / 幂等键

所有 Ads 表均使用：

```text
business_key_hash = sha256(canonical JSON of target_table + business_key fields)
```

各表业务键：

| reportTypeId | 目标表 | business key fields |
|---|---|---|
| `spCampaigns` | `amazon_ads_sp_campaign_daily` | `profile_id + report_date + campaign_id` |
| `spTargeting` | `amazon_ads_sp_targeting_daily` | `profile_id + report_date + campaign_id + ad_group_id + keyword_id + targeting + match_type` |
| `spSearchTerm` | `amazon_ads_sp_search_term_daily` | `profile_id + report_date + campaign_id + ad_group_id + keyword_id + targeting + search_term + match_type` |
| `spAdvertisedProduct` | `amazon_ads_sp_advertised_product_daily` | `profile_id + report_date + campaign_id + ad_group_id + advertised_asin + advertised_sku` |

使用 `business_key_hash` 而不是 `source_row_hash` 做 MERGE key。原因是 Amazon 可能在不同 report request 或不同文件顺序中返回同一业务行；使用业务键可以让同一逻辑日期/对象的指标被更新，而不是重复插入。

### 9.3 新 migration 需求

当前本功能没有阻塞性新 migration。已知非阻塞优化：

| 变化 | 原因 | migration 文件 | 状态 |
|---|---|---|---|
| 给 `amazon_sync_run_log` 增加 `rows_inserted` / `rows_updated` | 数据库审计细分 insert/update，而不只记录 rows_written | `004_add_sync_run_upsert_counts.sql` | optional/planned |
| 关联 `amazon_raw_report_file.id` 到 schema event 和 normalized rows | 提高 raw file 追溯稳定性 | 待定 | optional/planned |
| 新增 `amazon_ads_sp_purchased_product_daily` | 支持 `spPurchasedProduct` 非空样例后入库 | 待定 | wait for non-empty sample |

## 10. 幂等性设计

重复执行同一批 raw Ads 数据是安全的。

规则：

1. 每行必须有 `business_key_hash`；缺失则 skipped。
2. Repository 只允许写入 `ADS_TARGET_TABLE_SPECS` 中 allowlisted 表。
3. SQL 使用 `MERGE dbo.[table] WITH (HOLDLOCK)`。
4. 匹配条件是 `target.business_key_hash = source.business_key_hash`。
5. 匹配则 update 除 `business_key_hash` 外的所有目标列，并刷新 `updated_at`。
6. 不匹配则 insert。

已验证结果：

| 执行 | attempted | inserted | updated | written | skipped | 目标表总行数 |
|---|---:|---:|---:|---:|---:|---:|
| 第一次 `--execute` | 200 | 200 | 0 | 200 | 0 | 200 |
| 第二次同参数 `--execute` | 200 | 0 | 200 | 200 | 0 | 200 |

分表幂等性验证：

| 表 | 第一次 inserted | 第二次 updated | 当前行数 |
|---|---:|---:|---:|
| `amazon_ads_sp_campaign_daily` | 8 | 8 | 8 |
| `amazon_ads_sp_targeting_daily` | 99 | 99 | 99 |
| `amazon_ads_sp_search_term_daily` | 61 | 61 | 61 |
| `amazon_ads_sp_advertised_product_daily` | 32 | 32 | 32 |

## 11. Schema guard 与异常处理

### 11.1 Schema guard 来源

Expected schema 来自 Ads sampling plan。当前四类 table-ready report 使用严格字段匹配：

- `allow_extra_fields=False`
- 所有 expected fields 同时作为 required fields
- `allow_empty_report=True`

### 11.2 处理规则

| 场景 | 处理方式 | 是否阻塞入库 | 是否记录 validation event |
|---|---|---|---|
| observed fields 完全匹配 expected fields | `validation_status=ok`, `severity=info` | 否 | 是 |
| 缺少必需字段 | `missing_fields` | 是 | 是 |
| 出现新增字段 | `new_fields` | 是 | 是 |
| 同时缺失和新增 | `schema_drift` | 是 | 是 |
| 未注册 target table spec | `no_target_table_spec` | 是 | 否 |
| raw file 不存在 | `raw_file_not_found` | 是 | 否 |
| table spec `table_ready=False` | skip | 否 | 否 |
| 空报表且允许为空 | `empty_report`, `severity=info` | 否 | 是 |
| 数字解析失败 | parser 抛出异常 | 是 | 失败时写 sync_run_log error |
| 日期解析失败 | SQL 写入或 parser 阶段失败 | 是 | 失败时写 sync_run_log error |

### 11.3 requires_review

以下情况会设置或导致 `requires_review=True`，并阻断真实写库：

```text
missing_fields
new_fields
schema_drift
unmapped_fields
validation_failed
empty_report_unexpected
raw_file_not_found
no_target_table_spec
```

当前已验证 Ads 四类 report 的 validation event 均为：

```text
validation_status = ok
severity = info
requires_review = False
message = Observed report fields match the expected schema.
```

## 12. 审计与可追溯性

| 审计对象 | 表/字段 | 说明 |
|---|---|---|
| 任务运行 | `amazon_sync_run_log` | execute 模式先插入 running，再更新 success/failed。记录 rows_read、rows_written、rows_skipped、rows_failed。 |
| schema 检查 | `amazon_schema_validation_event` | 每个 reportTypeId 一条 validation event；当前 successful execute 写入 4 条。 |
| raw 文件路径 | `source_raw_file_path` | normalized 表中保存 raw file path。 |
| source report | `source_report_id` | 当前使用 raw file stem。 |
| source row | `source_row_index`, `source_row_hash` | 用于追溯原始行；不作为 upsert key。 |
| business key | `business_key_hash` | 用于幂等 MERGE。 |
| full raw row | `raw_data` | 保存完整源行 JSON。 |

当前审计缺口：

1. `amazon_schema_validation_event.raw_file_id` 当前为 `NULL`。
2. Ads normalized 表中的 `source_raw_file_id` 当前为 `NULL`。
3. `amazon_raw_report_file` 当前尚未由 Ads ingestion 正式登记 raw 文件。
4. `amazon_sync_run_log` 当前没有单独字段保存 inserted/updated，只保存 rows_written。

这些不是当前功能验收阻塞项，但应在后续优化中补齐。

## 13. 命令行入口

### 13.1 Dry-run

```bash
python scripts/ingest_ads_reports.py \
  --profile-id 3917953989967300 \
  --marketplace-id ATVPDKIKX0DER
```

默认不写数据库，只生成 preview 和 validation event JSONL。

### 13.2 Execute

```bash
python scripts/ingest_ads_reports.py \
  --profile-id 3917953989967300 \
  --marketplace-id ATVPDKIKX0DER \
  --execute
```

### 13.3 指定 report type

```bash
python scripts/ingest_ads_reports.py \
  --profile-id 3917953989967300 \
  --marketplace-id ATVPDKIKX0DER \
  --report-type-id spCampaigns
```

参数说明：

| 参数 | 是否必需 | 默认值 | 说明 |
|---|---|---|---|
| `--profile-id` | 否 | `.env` 中 `AMAZON_ADS_PROFILE_ID` | Amazon Ads profile ID。 |
| `--marketplace-id` | 否 | `.env` 中 `AMAZON_MARKETPLACE_ID` | 写入 normalized 表的 marketplace。 |
| `--report-type-id` | 否 | 所有 `table_ready=True` report | 可重复传入，限制本次处理的 reportTypeId。 |
| `--output-root` | 否 | `runtime/ingestion/amazon_ads` | preview 和 audit 本地输出目录。 |
| `--execute` | 否 | false | 不加时只 dry-run；加上后写 Azure SQL。 |
| `--allow-review` | 否 | false | 允许 CLI 在 requires_review 时不以非零退出；但数据库写入仍会被阻断。 |
| `--json-output` | 否 | none | 将 run result JSON 写到指定路径。 |

## 14. 相关代码路径

| 类型 | 路径 | 说明 |
|---|---|---|
| CLI | `scripts/ingest_ads_reports.py` | Ads ingestion dry-run / execute 入口。 |
| Service | `src/seller_data_pipeline/ingestion/ads_ingestion.py` | 真实写库编排、run log、commit/rollback。 |
| Dry-run service | `src/seller_data_pipeline/ingestion/ads_ingestion_dry_run.py` | 查找 raw file、schema guard、preview 生成。 |
| Mapping spec | `src/seller_data_pipeline/ingestion/ads_table_mapping.py` | reportTypeId 到 target table、columns、business key 的映射。 |
| Parser | `src/seller_data_pipeline/parsers/amazon/ads_report_parser.py` | Ads raw JSON 到 `AdsReportRecord`。 |
| Repository | `src/seller_data_pipeline/db/repositories/ads_repo.py` | Azure SQL allowlisted MERGE/upsert 和 audit insert/update。 |
| Schema guard | `src/seller_data_pipeline/sampling/schema_drift.py` | expected vs observed 字段验证。 |
| Sampling plan | `src/seller_data_pipeline/sampling/ads_report_sampling_plan.py` | Ads expected fields 来源。 |
| Unit tests | `tests/unit/parsers/amazon/test_ads_report_parser.py` | Parser 测试。 |
| Unit tests | `tests/unit/ingestion/test_ads_table_mapping.py` | 字段映射与 business key 测试。 |
| Unit tests | `tests/unit/ingestion/test_ads_ingestion_dry_run.py` | Dry-run guard 测试。 |
| Unit tests | `tests/unit/ingestion/test_ads_ingestion.py` | Execute 编排测试。 |
| Unit tests | `tests/unit/db/test_ads_repo.py` | Repository SQL 和 upsert 行为测试。 |

## 15. 测试计划

默认单元测试不依赖真实 Azure SQL 或真实 Amazon API：

```bash
PYTHONPATH=src pytest -q tests/unit/parsers/amazon/test_ads_report_parser.py
PYTHONPATH=src pytest -q tests/unit/ingestion/test_ads_table_mapping.py
PYTHONPATH=src pytest -q tests/unit/ingestion/test_ads_ingestion_dry_run.py
PYTHONPATH=src pytest -q tests/unit/ingestion/test_ads_ingestion.py
PYTHONPATH=src pytest -q tests/unit/db/test_ads_repo.py
PYTHONPATH=src pytest -q
python -m compileall -q scripts src tests
```

手工/集成验证需要本地 raw report 和 Azure SQL：

```bash
python scripts/ingest_ads_reports.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER
python scripts/ingest_ads_reports.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER --execute
python scripts/ingest_ads_reports.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER --execute
python scripts/check_database_status.py
```

## 16. 验收标准

本功能当前已通过以下验收：

1. dry-run 成功生成 preview。
2. `requires_review=False`。
3. execute 成功写入 Azure SQL。
4. 重复 execute 幂等性通过。
5. 四张目标表行数符合预期，总行数 200。
6. `amazon_sync_run_log` 记录本次任务。
7. `amazon_schema_validation_event` 记录四类 report 的 `ok` 结果。
8. 单元测试已覆盖 parser、mapping、dry-run、execute service 和 repository。
9. 本功能文档已更新为 `Implemented`。

## 17. 当前实现状态

| 日期 | 进展 | 证据/命令 | 备注 |
|---|---|---|---|
| 2026-05-16 | Ads dry-run 成功 | `python scripts/ingest_ads_reports.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER` | prepared_rows=200, requires_review=False。 |
| 2026-05-16 | 首次真实入库成功 | 同命令加 `--execute` | sync_run_id=1, inserted=200。 |
| 2026-05-16 | 幂等性验证通过 | 第二次执行同参数 `--execute` | sync_run_id=2, inserted=0, updated=200。 |
| 2026-05-16 | 四张表行数确认 | `scripts/check_database_status.py` 或 SQL count | 8 + 99 + 61 + 32 = 200。 |
| 2026-05-16 | Schema validation event 确认 | 查询 `amazon_schema_validation_event` | 四类 report 均 ok/info/requires_review=False。 |
| 2026-05-16 | 正式功能文档完成第一版 | `docs/features/feature_ads_ingestion.md` | 本文档。 |

## 18. 后续优化

- 写入 `amazon_raw_report_file`，并把 `source_raw_file_id` / `raw_file_id` 关联到 normalized 表和 schema validation event。
- 在 `amazon_sync_run_log` 增加 `rows_inserted` / `rows_updated`，让数据库侧也能记录 upsert 明细。
- 将 `validation_stage` 从 `pre_ingestion_dry_run` 优化为更中性的 `pre_ingestion_schema_check`；当前名称不影响功能。
- 增加 `spPurchasedProduct` 非空样例采集；确认字段后再新增表和入库链路。
- 后续可增加 derived metrics，例如 CTR、CPC、ACOS、ROAS，但建议放在分析/报表层，不直接改当前 raw performance 表。
- 后续上 Azure Container Apps Jobs 时，把本 CLI 封装为 scheduled job，并将 secret 管理迁移到 Azure Secret/Key Vault 方案。

## 19. 弃置记录

| 日期 | 弃置内容 | 原因 | 替代方案 |
|---|---|---|---|
| 2026-05-16 | 将 `source_row_hash` 作为 upsert key | 同一业务行在不同 report request 或不同文件排序下 row_index 可能变化，会导致重复插入 | 使用 `business_key_hash`。 |
| 2026-05-16 | 在 `spPurchasedProduct` 空样例基础上直接建表入库 | 空数组不能证明真实字段结构；贸然建表容易偏移 | 等待非空样例后新增功能和 migration。 |
| 2026-05-16 | 没有 dry-run 直接写 Ads 表 | Amazon Ads schema 可能变化，直接写库风险高 | schema guard + preview 通过后才允许 `--execute`。 |
