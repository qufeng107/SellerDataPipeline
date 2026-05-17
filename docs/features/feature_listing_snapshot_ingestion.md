# Feature: SP-API Listing 快照入库

> 文档状态：正式功能设计文档  
> 负责人：AI assisted / Zifei 复核  
> 更新时间：2026-05-16  
> 功能状态：Implemented，dry-run / schema guard / repository / Azure SQL execute / idempotency verified  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关基础设施功能：`docs/features/feature_azure_sql_foundation.md`  
> 参考实现样板：`docs/features/feature_ads_ingestion.md`

---

## 1. 功能摘要

本功能负责把 SP-API Reports 的 `GET_MERCHANT_LISTINGS_ALL_DATA` flat file 转换为 Azure SQL 中的 `dbo.amazon_listing_snapshot` 快照表，用于沉淀 SKU、ASIN、listing id、标题、价格、履约渠道和 listing 状态等基础经营数据。

当前真实状态是：该 report 已完成取样并有 6 行真实样例；`ListingsAllDataParser` 已实现并有单元测试；Azure SQL 中 `amazon_listing_snapshot` 表已由 `001_create_core_tables.sql` 创建；`003_add_listing_snapshot_business_key_hash.sql` 已在 Azure SQL 执行成功，表结构已具备 `business_key_hash` 幂等键和唯一过滤索引。本功能已新增 Listing dry-run preview、schema guard、DB-ready mapping、repository/upsert、CLI 与单元测试；本地 dry-run 使用真实 raw file 验证通过，`prepared_rows=6`、`requires_review=False`。用户本地 Azure SQL 已完成首次真实写入和第二次重复 execute 幂等性验证：首次 `inserted=6 updated=0`，第二次 `inserted=0 updated=6`。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 数据源取样 | 已完成 |
| Parser | 已完成 |
| Dry-run preview | 已实现，本地真实样例 dry-run 通过 |
| Schema guard | 已实现，当前 29 列样例校验 `ok` |
| Repository/upsert | 已实现并通过 Azure SQL execute 验证 |
| Azure SQL execute | 已完成，首次写入 `inserted=6 updated=0` |
| 幂等性验证 | 已完成，第二次 execute `inserted=0 updated=6` |
| 单元测试 | Parser、mapping、dry-run、repository、ingestion audit event 已覆盖 |
| 文档同步 | 已同步 003 migration、代码实现、execute 和幂等性验收结果 |

功能整体状态：`Implemented`。Listing 入库已经完成 dry-run、schema guard、Azure SQL execute、第二次 execute 幂等性验证和文档同步。

## 3. 业务目标

Listing 快照是后续几乎所有运营分析的基础维度表之一。它帮助公司回答：

1. 当前店铺有哪些 seller SKU 和 ASIN。
2. 每个 SKU 的 listing id、标题、价格、状态是否可售。
3. SKU 当前是 FBA / Amazon 履约还是其他履约渠道。
4. 哪些 listing 是 Active、Inactive、Incomplete 等状态。
5. 后续库存、广告、订单、结算数据如何通过 seller SKU / ASIN 与商品基础信息关联。

对当前小体量跨境电商公司来说，本功能优先级较高，因为它是连接“商品基础资料”和后续“库存、销售、广告、财务、利润核算”的基础。没有稳定的 listing 快照，后续报表容易只看到 SKU/ASIN 代码，缺少标题、状态、价格等运营上下文。

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 `GET_MERCHANT_LISTINGS_ALL_DATA` raw flat file。
- 校验 listing report 的字段结构是否符合当前已取样 schema。
- 使用 `ListingsAllDataParser` 解析核心字段。
- 生成 DB-ready dry-run preview。
- 将 listing 快照写入 `dbo.amazon_listing_snapshot`。
- 写入 `amazon_sync_run_log`。
- 写入 `amazon_schema_validation_event`。
- 支持重复执行幂等 upsert。
- 保留 `raw_data`、`source_raw_file_path`、`source_report_id`、`source_row_hash` 等追溯字段。

### 4.2 本功能不包含

- 不负责提交/下载 SP-API report request；提交和下载属于 SP-API data access / sampling 能力。
- 不负责 FBA 可售库存、不可售库存、预留库存、入库数量等库存口径；这些应由 `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` 和库存相关功能处理。
- 不负责销售、订单、结算、利润核算。
- 不负责自动修改 Amazon listing、价格或库存。
- 不负责图片 URL、zshop 旧字段、国际配送等低优先级或当前样例为空字段的结构化建模；这些字段保留在 `raw_data`，需要时另行设计。
- 不负责 Azure Container Apps Jobs 定时运行；当前阶段先实现本地 CLI + Azure SQL 写库闭环。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports | `GET_MERCHANT_LISTINGS_ALL_DATA` | tab-delimited flat file | 已取样，6 行，29 列 | Parser、dry-run、schema guard、repository、CLI、execute 和幂等性验证已完成 | SKU/ASIN/listing/价格/状态基础信息。 |

当前样例记录：

| 项目 | 当前值 |
|---|---|
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_MERCHANT_LISTINGS_ALL_DATA/2026-05-13/112285020586.txt` |
| encoding | `utf-8-sig` |
| delimiter | tab |
| row_count | `6` |
| column_count | `29` |
| sample doc | `requirements_to_be_deprecated/data_samples/GET_MERCHANT_LISTINGS_ALL_DATA.md` |

当前 raw 路径约定：

```text
reports/raw/amazon/{marketplace_id}/{report_type}/{date}/{report_id}.txt
```

## 6. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/sp_api/GET_MERCHANT_LISTINGS_ALL_DATA/{marketplace_id}/{timestamp}/...` | 本次 dry-run / execute 汇总。 |
| Schema events JSONL | `runtime/ingestion/sp_api/GET_MERCHANT_LISTINGS_ALL_DATA/{marketplace_id}/{timestamp}/schema_validation_events.jsonl` | 入库前字段验证结果。 |
| Preview rows | `runtime/ingestion/sp_api/GET_MERCHANT_LISTINGS_ALL_DATA/{marketplace_id}/{timestamp}/previews/*.preview.jsonl` | DB-ready preview，不加 `--execute` 时只生成这些文件。 |
| Azure SQL table | `dbo.amazon_listing_snapshot` | Listing 日快照/取样日快照。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录本 report 的 schema guard 结果。 |

说明：上面的 runtime 路径已由 `scripts/ingest_listing_snapshot.py` dry-run 验证，当前真实样例输出 `prepared_rows=6`、`requires_review=False`。

## 7. 处理流程

建议按 Ads 入库链路复用相同阶段：

```text
local raw SP-API listing flat file
  -> find latest raw file for marketplace/report_type, or accept --raw-file explicit path
  -> analyze observed fields
  -> compare with expected listing schema
  -> if requires_review=True: block database write
  -> parse raw rows into ListingSnapshotRecord
  -> compute business_key_hash
  -> write DB-ready preview JSONL
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE preview rows into amazon_listing_snapshot by business_key_hash
  -> insert schema validation event
  -> update amazon_sync_run_log final status
  -> commit transaction
```

关键行为：

1. 默认模式必须是 dry-run，不写数据库。
2. 只有显式传入 `--execute` 才允许连接 Azure SQL 并写库。
3. 如果 schema guard 产生 `requires_review=True`，真实写库必须被阻断。
4. 写库时先创建 running 状态的 sync run，再 upsert，最后更新 success/failed。
5. 如果 upsert 阶段异常，应 rollback，并尽量写失败审计。
6. 本功能不能直接复用 `source_row_hash` 作为幂等键；应使用业务键或 `business_key_hash`。

## 8. 字段映射

### 8.1 源字段到标准字段

| 源字段 | 标准字段 | 类型 | 是否必需 | 当前处理 | 说明 |
|---|---|---|---|---|---|
| `listing-id` | `listing_id` | string | yes | mapped | Amazon listing id。 |
| `seller-sku` | `seller_sku` | string | yes | mapped | 卖家 SKU。 |
| `asin1` | `asin` | string | yes for current parser | mapped | 主 ASIN。 |
| `product-id` | `product_id` | string | yes for current parser | mapped | 产品标识；当前样例通常等于 ASIN。 |
| `product-id-type` | `product_id_type` | string/enum code | yes for current parser | mapped | 当前样例为 `1`。 |
| `item-name` | `item_name` | string | yes for current parser | mapped | 商品标题。 |
| `item-description` | `item_description` | string | no | mapped | 商品描述，可能很长。 |
| `price` | `price` | decimal | yes for current parser | mapped | 当前样例存在空值，解析为空时写 NULL。 |
| report/default | `currency` | string | no | derived | 当前 parser 默认 `USD`，后续可由 marketplace metadata 解析。 |
| `quantity` | `quantity` | int | no | mapped | 当前 FBA 样例为空；不能作为 FBA 库存主口径。 |
| `pending-quantity` | `pending_quantity` | int | no | mapped | 当前样例为空。 |
| `open-date` | `open_date_raw` | string | yes for current parser | mapped | 原始字符串保留，例如带 `PST`。 |
| `open-date` | `open_date_utc` | datetime | no | deferred | 当前 parser 尚未解析为 UTC；本轮不强转。 |
| `item-is-marketplace` | `item_is_marketplace` | boolean | yes for current parser | mapped | `y/yes/true/1` -> true，`n/no/false/0` -> false。 |
| `item-condition` | `item_condition` | string/enum code | yes for current parser | mapped | 当前样例有 `11`、`500`。 |
| `fulfillment-channel` | `fulfillment_channel` | string | yes for current parser | mapped | 当前样例为 `AMAZON_NA`。 |
| `merchant-shipping-group` | `merchant_shipping_group` | string | no | mapped | 当前样例为 `Migrated Template`。 |
| `status` | `status` | string | yes for current parser | mapped | 当前样例含 `Active`、`Inactive`、`Incomplete`。 |
| `image-url` | n/a | string | no | deferred/raw only | 当前样例为空；保留在 raw_data。 |
| `zshop-shipping-fee` | n/a | string | no | deferred/raw only | 当前样例为空；旧字段，暂不结构化。 |
| `item-note` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `zshop-category1` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `zshop-browse-path` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `zshop-storefront-feature` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `asin2` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `asin3` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `will-ship-internationally` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `expedited-shipping` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `zshop-boldface` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `bid-for-featured-placement` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| `add-delete` | n/a | string | no | deferred/raw only | 当前样例为空。 |
| raw row object | `raw_data` | JSON string | yes | mapped | 完整保留源行，便于后续补字段。 |

解析规则：

- flat file 使用 `decode_report_content` 自动识别编码，使用 `detect_report_delimiter` 识别分隔符。
- 当前样例为 tab-delimited。
- 空字符串统一转为 `None`。
- `price` 使用 `Decimal`；非法 decimal 应阻断本次入库。
- `quantity` / `pending_quantity` 使用 int；非法 int 应阻断本次入库。
- `item-is-marketplace` 使用 yes/no parser；非预期值应阻断本次入库。
- `open_date_utc` 当前不强转，避免时区字符串规则不稳定导致错误入库；先保存 `open_date_raw`。
- `raw_data` 必须保存完整源行。

### 8.2 标准字段到数据库字段

| 标准字段 | 目标表 | 目标字段 | 类型 | 转换规则 |
|---|---|---|---|---|
| `marketplace_id` | `dbo.amazon_listing_snapshot` | `marketplace_id` | `NVARCHAR(50)` | CLI 参数或 `.env`。 |
| `snapshot_date` | `dbo.amazon_listing_snapshot` | `snapshot_date` | `DATE` | CLI 参数、raw file 日期目录或默认处理日期；应在 CLI 中显式支持。 |
| `listing_id` | `dbo.amazon_listing_snapshot` | `listing_id` | `NVARCHAR(200)` | 来自 `listing-id`。 |
| `seller_sku` | `dbo.amazon_listing_snapshot` | `seller_sku` | `NVARCHAR(200)` | 来自 `seller-sku`。 |
| `asin` | `dbo.amazon_listing_snapshot` | `asin` | `NVARCHAR(50)` | 来自 `asin1`。 |
| `product_id` | `dbo.amazon_listing_snapshot` | `product_id` | `NVARCHAR(100)` | 来自 `product-id`。 |
| `product_id_type` | `dbo.amazon_listing_snapshot` | `product_id_type` | `NVARCHAR(50)` | 来自 `product-id-type`。 |
| `item_name` | `dbo.amazon_listing_snapshot` | `item_name` | `NVARCHAR(1000)` | 来自 `item-name`。 |
| `item_description` | `dbo.amazon_listing_snapshot` | `item_description` | `NVARCHAR(MAX)` | 来自 `item-description`。 |
| `price` | `dbo.amazon_listing_snapshot` | `price` | `DECIMAL(18,4)` | 来自 `price`。 |
| `currency` | `dbo.amazon_listing_snapshot` | `currency` | `NVARCHAR(10)` | 初期使用 marketplace 默认币种，US 为 `USD`。 |
| `quantity` | `dbo.amazon_listing_snapshot` | `quantity` | `INT` | 来自 `quantity`，可为空。 |
| `pending_quantity` | `dbo.amazon_listing_snapshot` | `pending_quantity` | `INT` | 来自 `pending-quantity`，可为空。 |
| `open_date_raw` | `dbo.amazon_listing_snapshot` | `open_date_raw` | `NVARCHAR(100)` | 来自 `open-date` 原文。 |
| `open_date_utc` | `dbo.amazon_listing_snapshot` | `open_date_utc` | `DATETIME2` | 当前先写 NULL，后续若规则稳定再补。 |
| `item_is_marketplace` | `dbo.amazon_listing_snapshot` | `item_is_marketplace` | `BIT` | 来自 `item-is-marketplace`。 |
| `item_condition` | `dbo.amazon_listing_snapshot` | `item_condition` | `NVARCHAR(50)` | 来自 `item-condition`。 |
| `fulfillment_channel` | `dbo.amazon_listing_snapshot` | `fulfillment_channel` | `NVARCHAR(100)` | 来自 `fulfillment-channel`。 |
| `merchant_shipping_group` | `dbo.amazon_listing_snapshot` | `merchant_shipping_group` | `NVARCHAR(200)` | 来自 `merchant-shipping-group`。 |
| `status` | `dbo.amazon_listing_snapshot` | `status` | `NVARCHAR(50)` | 来自 `status`。 |
| `source_system` | `dbo.amazon_listing_snapshot` | `source_system` | `NVARCHAR(50)` | 固定 `sp_api_reports`。 |
| `source_report_type` | `dbo.amazon_listing_snapshot` | `source_report_type` | `NVARCHAR(120)` | 固定 `GET_MERCHANT_LISTINGS_ALL_DATA`。 |
| `source_report_id` | `dbo.amazon_listing_snapshot` | `source_report_id` | `NVARCHAR(120)` | Amazon report id；本地 raw file stem 可作为 fallback。 |
| `source_raw_file_path` | `dbo.amazon_listing_snapshot` | `source_raw_file_path` | `NVARCHAR(1000)` | 本地 raw file 路径。 |
| `source_run_id` | `dbo.amazon_listing_snapshot` | `source_run_id` | `BIGINT` | 对应 `amazon_sync_run_log.id`。 |
| `source_row_hash` | `dbo.amazon_listing_snapshot` | `source_row_hash` | `NVARCHAR(100)` | SHA256 canonical raw row。 |
| `business_key_hash` | `dbo.amazon_listing_snapshot` | `business_key_hash` | `NVARCHAR(100)` | 建议新增；SHA256 canonical business key。 |
| `raw_data` | `dbo.amazon_listing_snapshot` | `raw_data` | `NVARCHAR(MAX)` | 完整源行 JSON。 |

## 9. 目标数据表设计

### 9.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.amazon_listing_snapshot` | yes | SKU/ASIN/listing 状态、标题、价格、履约渠道快照 | planned MERGE/upsert |
| `dbo.amazon_sync_run_log` | yes | 任务审计 | insert then update |
| `dbo.amazon_schema_validation_event` | yes | schema guard 审计 | append-only insert |
| `dbo.amazon_raw_report_file` | yes | raw file registry | 后续应写入；本功能首版可先保存 path/hash |

### 9.2 业务主键 / 幂等键

建议业务键：

```text
business_key = marketplace_id + snapshot_date + seller_sku + listing_id
business_key_hash = sha256(canonical JSON of business_key)
```

设计原因：

1. `seller_sku` 是运营主键，但同一 SKU 理论上可能在不同 marketplace 或不同 snapshot date 出现不同状态。
2. `listing_id` 可进一步区分 Amazon listing 维度。
3. `asin`、标题、价格、状态等是可变属性，不应作为 upsert key。
4. `source_row_hash` 只代表 raw row 内容；价格或状态变化会改变 source row hash，不适合作为同一业务行的 upsert key。
5. SQL Server 对长 `NVARCHAR` 组合唯一索引有长度风险，使用 `business_key_hash` 更稳定，也与 Ads 已验证模式一致。

### 9.3 已执行 schema migration

当前真实表 `amazon_listing_snapshot` 已通过独立 migration 补齐 Ads 表中已验证有效的 `business_key_hash` 字段和唯一过滤索引。该 migration 已在 Azure SQL `amazon_ops` 执行成功，开发 repository 时可以直接使用该字段作为 MERGE/upsert 匹配键：

| 变化 | 原因 | migration 文件 | 状态 |
|---|---|---|---|
| 新增 `business_key_hash NVARCHAR(100) NULL` 到 `dbo.amazon_listing_snapshot` | 稳定支持幂等 MERGE/upsert；nullable 设计保证即使表已有旧数据也能安全执行 | `003_add_listing_snapshot_business_key_hash.sql` | executed, 3/3 batches |
| 新增唯一过滤索引 `UX_amazon_listing_snapshot_business_key_hash` on `business_key_hash WHERE business_key_hash IS NOT NULL` | 数据库层防止已写入业务行重复，同时允许历史空值等待回填 | `003_add_listing_snapshot_business_key_hash.sql` | executed, 3/3 batches |

注意：

- `docs/database/database_current_schema_spec.md` 已同步记录 `business_key_hash` 字段和 `UX_amazon_listing_snapshot_business_key_hash` 索引为当前事实。
- migration 采用 nullable column + filtered unique index，是为了比 `NOT NULL` 一步到位更安全；repository 写入时仍必须要求每一行生成非空 `business_key_hash`。
- 如果未来已经存在旧 listing 行且 `business_key_hash` 为 NULL，应另写 backfill migration 或维护脚本，不能靠修改 003 文件处理。
- 不允许修改已执行的 `001_create_core_tables.sql`、`002_create_indexes.sql` 和 `003_add_listing_snapshot_business_key_hash.sql`。

## 10. 幂等性设计

重复执行同一批 listing raw 文件必须安全。

目标规则：

1. 每行必须有 `business_key_hash`；缺失则 skipped 或阻断本次写库。
2. SQL 使用 `MERGE dbo.amazon_listing_snapshot WITH (HOLDLOCK)`。
3. 匹配条件是 `target.business_key_hash = source.business_key_hash`。
4. 匹配则 update 可变字段，例如 `asin`、`product_id`、`item_name`、`price`、`quantity`、`status`、`raw_data`、`source_*`，并刷新 `updated_at`。
5. 不匹配则 insert。
6. `created_at` 只在 insert 时生成，update 不应覆盖。

验收目标：

```text
第一次 execute: inserted=N, updated=0, target row count=N
第二次同参数 execute: inserted=0, updated=N 或 skipped=N, target row count 仍为 N
```

对于 listing 快照，建议首版采用 `updated=N` 模式，与 Ads repository 保持一致；后续若要优化为完全相同数据 `skipped=N`，需要先统一所有 repository 的变更检测策略。

## 11. Schema guard 与异常处理

### 11.1 Expected schema

建议为 `GET_MERCHANT_LISTINGS_ALL_DATA` 注册 SP-API expected schema。

当前已观察 29 个源字段：

```text
item-name
item-description
listing-id
seller-sku
price
quantity
open-date
image-url
item-is-marketplace
product-id-type
zshop-shipping-fee
item-note
item-condition
zshop-category1
zshop-browse-path
zshop-storefront-feature
asin1
asin2
asin3
will-ship-internationally
expedited-shipping
zshop-boldface
product-id
bid-for-featured-placement
add-delete
pending-quantity
fulfillment-channel
merchant-shipping-group
status
```

建议 required fields 使用当前 parser 必需字段：

```text
listing-id
seller-sku
asin1
product-id
product-id-type
item-name
price
open-date
item-condition
fulfillment-channel
status
```

建议 schema guard 参数：

| 参数 | 建议值 | 说明 |
|---|---|---|
| `source_system` | `sp_api_reports` | 区分 Ads。 |
| `report_type` | `GET_MERCHANT_LISTINGS_ALL_DATA` | SP-API report type。 |
| `expected_fields` | 29 个当前已观察字段 | 用于发现 Amazon 新增字段。 |
| `required_fields` | parser 当前必需字段 | 缺少这些字段阻断入库。 |
| `allow_extra_fields` | `False` | 出现新字段时先阻断，人工复核映射。 |
| `allow_empty_report` | `True` | 空 listing report 可记录，但不写业务行。 |

### 11.2 处理规则

| 场景 | 处理方式 | 是否阻塞入库 | 是否记录 validation event |
|---|---|---|---|
| observed fields 符合 expected/required | `validation_status=ok`, `severity=info` | 否 | 是 |
| 缺少 required field | `missing_fields` | 是 | 是 |
| 出现新增字段 | `new_fields` | 是 | 是 |
| 无 expected schema | `no_expected_schema` | 是，直到本功能明确注册 schema | 是 |
| 空 report 且允许为空 | `empty_report`, `severity=info` | 不写业务表 | 是 |
| delimiter 无法识别 | parser 抛出异常 | 是 | 失败时写 sync_run_log error |
| decimal/int/bool 解析失败 | parser 抛出异常 | 是 | 失败时写 sync_run_log error |
| Azure SQL upsert 失败 | rollback | 是 | 写 sync_run_log failed |

### 11.3 requires_review

以下情况应设置或导致 `requires_review=True`，并阻断真实写库：

```text
missing_fields
new_fields
schema_drift
unmapped_fields
validation_failed
no_expected_schema
parser_failed
upsert_failed
```

## 12. 审计与可追溯性

| 审计对象 | 表/字段 | 说明 |
|---|---|---|
| 任务运行 | `amazon_sync_run_log` | execute 模式先插入 running，再更新 success/failed。记录 rows_read、rows_written、rows_skipped、rows_failed。 |
| schema 检查 | `amazon_schema_validation_event` | 每次处理 listing report 应记录一条 validation event。 |
| raw 文件路径 | `source_raw_file_path` | normalized 表中保存 raw file path。 |
| source report | `source_report_id` | Amazon report id；如果不可得，可用 raw file stem。 |
| source row | `source_row_hash` | 原始行 hash，用于追溯，不作为 upsert key。 |
| business key | `business_key_hash` | 用于幂等 MERGE。 |
| full raw row | `raw_data` | 保存完整源行 JSON。 |

当前待补审计能力：

1. 首版可以先保存 `source_raw_file_path`，但后续应正式写入 `amazon_raw_report_file` 并关联 `source_raw_file_id`。
2. SP-API report request manifest 与 `amazon_report_request` 表的关系尚未完整打通；后续应让 `source_report_request_id` 可追溯。
3. `amazon_sync_run_log` 目前没有 `rows_inserted` / `rows_updated`，首版可沿用 rows_written；后续可通过统一 migration 补强。

## 13. 命令行入口

本功能已新增专用 CLI：

```text
scripts/ingest_listing_snapshot.py
```

首版先使用专用 Listing CLI，而不是通用 `ingest_sp_api_reports.py`。这是一个流程上的小调整：当前只有 Listing 完成设计和 migration，专用入口可以降低误把未实现 SP-API report 写库的风险；未来 Inventory / Sales & Traffic 等功能成熟后，再评估是否抽象成通用 SP-API ingestion 入口。

### 13.1 Dry-run

```bash
python scripts/ingest_listing_snapshot.py \
  --marketplace-id ATVPDKIKX0DER
```

当前本地真实样例 dry-run 已通过：

```text
Listing ingestion mode=dry_run status=dry_run_success
prepared_rows=6 requires_review=False sync_run_id=None
```

### 13.2 Execute

```bash
python scripts/ingest_listing_snapshot.py \
  --marketplace-id ATVPDKIKX0DER \
  --execute
```

### 13.3 指定 raw file 和 snapshot date

```bash
python scripts/ingest_listing_snapshot.py \
  --marketplace-id ATVPDKIKX0DER \
  --raw-file reports/raw/amazon/ATVPDKIKX0DER/GET_MERCHANT_LISTINGS_ALL_DATA/2026-05-13/112285020586.txt \
  --snapshot-date 2026-05-13
```

参数说明：

| 参数 | 是否必需 | 默认值 | 说明 |
|---|---|---|---|
| `--marketplace-id` | 否 | `.env` 中 `AMAZON_MARKETPLACE_ID` | 写入 normalized 表。 |
| `--raw-file` | 否 | 自动查找最新 raw file | 指定本次处理的 raw file，便于验收。 |
| `--snapshot-date` | 否 | raw file 日期目录或当天日期 | 写入 `snapshot_date`。建议验收时显式传入。 |
| `--currency` | 否 | `USD` | 写入 `currency`。US marketplace 首版默认 USD。 |
| `--output-root` | 否 | `runtime/ingestion/sp_api` | preview 和 audit 本地输出目录。 |
| `--execute` | 否 | dry-run | 显式写 Azure SQL。未传时绝不写数据库。 |
| `--allow-review` | 否 | false | schema review 时不以非零退出；但仍阻断真实写库。 |
| `--json-output` | 否 | 无 | 输出本次 run result JSON。 |
| `--execute` | 否 | false | 不加时只 dry-run；加上后写 Azure SQL。 |
| `--allow-review` | 否 | false | 可允许 CLI 输出 review 结果，但数据库写入仍应被阻断。 |
| `--json-output` | 否 | none | 将 run result JSON 写到指定路径。 |

提交和下载 report 的现有命令仍是数据接入层命令，不属于本功能 CLI：

```bash
PYTHONPATH=src python scripts/submit_report_requests.py \
  --report-type GET_MERCHANT_LISTINGS_ALL_DATA

PYTHONPATH=src python scripts/collect_ready_reports.py --limit 10
```

## 14. 相关代码路径

| 类型 | 路径 | 说明 |
|---|---|---|
| Existing parser | `src/seller_data_pipeline/parsers/amazon/listings_all_data_parser.py` | 已实现 raw flat file -> `ListingSnapshotRecord`。 |
| Existing parser tests | `tests/unit/parsers/amazon/test_listings_all_data_parser.py` | 已覆盖核心字段映射和缺字段报错。 |
| Existing SP-API submit CLI | `scripts/submit_report_requests.py` | 提交 SP-API report request；不是入库入口。 |
| Existing SP-API collect CLI | `scripts/collect_ready_reports.py` | 下载 DONE report 到 raw 文件；不是入库入口。 |
| Listing CLI | `scripts/ingest_listing_snapshot.py` | 已新增；Listing 快照 dry-run / execute 入口。 |
| Listing dry-run service | `src/seller_data_pipeline/ingestion/listing_ingestion_dry_run.py` | 已新增；查找 raw file、schema guard、preview 和 audit manifest。 |
| Listing execute service | `src/seller_data_pipeline/ingestion/listing_ingestion.py` | 已新增；默认 dry-run，显式 `--execute` 才写 Azure SQL。 |
| Listing mapping | `src/seller_data_pipeline/ingestion/listing_table_mapping.py` | 已新增；expected schema、table columns、business key hash 和 preview JSONL。 |
| Listing repository | `src/seller_data_pipeline/db/repositories/listing_repo.py` | 已新增；allowlist `amazon_listing_snapshot`，使用 `MERGE ... WITH (HOLDLOCK)`。 |
| Existing schema guard | `src/seller_data_pipeline/sampling/schema_drift.py` | 需扩展 SP-API expected schema。 |
| Existing raw analyzer | `src/seller_data_pipeline/sampling/report_analyzer.py` | 可复用字段分析能力。 |
| Current table spec | `docs/database/database_current_schema_spec.md` | 当前真实表结构；migration 成功后再更新。 |

## 15. 测试计划

### 15.1 已有测试

```bash
PYTHONPATH=src pytest -q tests/unit/parsers/amazon/test_listings_all_data_parser.py
```

### 15.2 本功能开发后必须新增/通过的测试

已新增并通过：

```bash
PYTHONPATH=src pytest -q tests/unit/ingestion/test_listing_table_mapping.py
PYTHONPATH=src pytest -q tests/unit/ingestion/test_listing_ingestion_dry_run.py
PYTHONPATH=src pytest -q tests/unit/ingestion/test_listing_ingestion.py
PYTHONPATH=src pytest -q tests/unit/db/test_listing_repo.py
PYTHONPATH=src pytest -q
python -m compileall -q scripts src tests
```

测试重点：

1. listing report expected schema 正确注册。
2. 新字段/缺字段会产生 `requires_review=True`。
3. parser 输出字段能完整映射到 preview row。
4. `business_key_hash` 基于 `marketplace_id + snapshot_date + seller_sku + listing_id` 稳定生成。
5. repository 只允许写入 allowlisted 表。
6. 首次 execute insert，第二次 execute update 或 skip，目标表总行数不变。
7. execute 失败时 rollback 并写失败审计。

## 16. 验收标准

本功能完成时，必须满足：

1. `GET_MERCHANT_LISTINGS_ALL_DATA` dry-run 能找到 raw file 并生成 preview。已通过，当前样例 `prepared_rows=6`。
2. `requires_review=False`。已通过。
3. preview 行数等于 raw report 行数。已通过，当前样例 6 行。
4. `amazon_listing_snapshot` 首次真实入库成功。已完成：`sync_run_id=3`, `inserted=6`, `updated=0`。
5. 重复执行同一 raw file 幂等性通过，不重复插入。已完成：`sync_run_id=4`, `inserted=0`, `updated=6`。
6. `amazon_sync_run_log` 记录本次任务。
7. `amazon_schema_validation_event` 记录本 report 的 `ok` 事件。
8. 如执行了 `003_add_listing_snapshot_business_key_hash.sql`，必须更新 `docs/database/database_current_schema_spec.md`。
9. 单元测试通过。
10. `docs/project/progress_next_steps.md` 更新最新验收结果。

首轮验收建议使用当前样例文件，预期行数为 6：

```text
第一次 execute: sync_run_id=3, attempted=6, inserted=6, updated=0
第二次 execute: sync_run_id=4, attempted=6, inserted=0, updated=6
amazon_listing_snapshot target row count=6
```

如果后续使用更新的 raw file，验收行数应以实际 raw report 行数为准，并在进度文档中记录。

## 17. 当前实现状态

| 日期 | 进展 | 证据/命令 | 备注 |
|---|---|---|---|
| 2026-05-13 | `GET_MERCHANT_LISTINGS_ALL_DATA` 已取样 | `requirements_to_be_deprecated/data_samples/GET_MERCHANT_LISTINGS_ALL_DATA.md` | 6 行，29 列。 |
| 2026-05-16 | Azure SQL 目标表已存在 | `docs/database/database_current_schema_spec.md` | 由 `001_create_core_tables.sql` 创建。 |
| 2026-05-16 | Parser 已有单元测试 | `tests/unit/parsers/amazon/test_listings_all_data_parser.py` | 覆盖核心字段和缺字段。 |
| 2026-05-16 | 本功能设计文档完成第一版 | `docs/features/feature_listing_snapshot_ingestion.md` | 本文档。 |
| 2026-05-16 | 003 migration 已执行成功 | `python scripts/run_sql_migration.py --file sql/migrations/003_add_listing_snapshot_business_key_hash.sql` | 3/3 batches；current schema spec 已更新为事实。 |
| 2026-05-16 | Listing dry-run / mapping / repository / CLI 已新增 | `scripts/ingest_listing_snapshot.py` 等 | 真实 raw file dry-run 通过：`prepared_rows=6`、`requires_review=False`。 |
| 2026-05-16 | Listing 首次 Azure SQL execute 通过 | `python scripts/ingest_listing_snapshot.py --marketplace-id ATVPDKIKX0DER --execute` | `sync_run_id=3`, `attempted=6`, `inserted=6`, `updated=0`。 |
| 2026-05-16 | Listing 第二次 execute 幂等性通过 | 同一命令重复执行 | `sync_run_id=4`, `attempted=6`, `inserted=0`, `updated=6`。 |
| 2026-05-16 | 单元测试通过 | `PYTHONPATH=src pytest -q` | 118 passed；`compileall` 通过；当前环境未安装 `ruff`，未能本地执行 ruff。 |

## 18. 下一步开发任务

本功能已完成当前阶段开发和验收，不再作为下一条主线。后续仅在以下情况回到本文档：

1. Listing 源 report 字段发生变化，schema guard 出现 `requires_review=True`。
2. 需要新增 listing 相关字段、索引或 reporting view。
3. 需要把 raw file 正式登记到 `amazon_raw_report_file` 并关联 `source_raw_file_id`。
4. 需要支持非 US marketplace，且字段结构或币种/日期规则与当前不同。

下一条主线 Inventory normalized ingestion 已进入实现阶段：`docs/features/feature_inventory_ingestion.md` 已建立，`sql/migrations/004_add_inventory_daily_business_key_hash.sql` 已执行并同步 current schema spec，专用入口、mapping、repository 和 dry-run 已完成。下一步应执行 Inventory 真实 `--execute` 和第二次幂等性验证。

## 19. 后续优化

- 将 `open_date_raw` 稳定解析为 `open_date_utc`，但必须先确认 Amazon 在不同 marketplace/timezone 下的格式。
- 从 `amazon_marketplace` 表或配置中派生 currency，而不是 parser 默认写死 `USD`。
- 正式登记 `amazon_raw_report_file`，并把 `source_raw_file_id` 写入 normalized 表。
- 与 `amazon_inventory_daily`、Ads SKU/ASIN 表、订单和结算表建立 reporting 层关联。
- 如果未来需要保留 listing 历史变化，可在 reporting 层区分“每日快照”和“当前最新状态视图”。
- 如果 Amazon listing report 在不同 marketplace 有额外字段，应先通过 schema validation 阻断，再更新 data_access 和本功能文档。

## 20. 弃置记录

| 日期 | 弃置内容 | 原因 | 替代方案 |
|---|---|---|---|
| 2026-05-16 | 把 `quantity` 当作 FBA 库存主口径 | 当前 listing 样例中 FBA 商品 `quantity` 为空，不能代表 FBA 可售库存 | 使用 `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` 实现库存功能。 |
| 2026-05-16 | 使用 `source_row_hash` 作为 upsert key | 价格、状态或标题变化会改变 raw row hash，导致同一业务行重复插入 | 使用 `business_key_hash`。 |
| 2026-05-16 | 在没有 schema guard 的情况下直接写 `amazon_listing_snapshot` | Amazon report 字段可能变化，直接写库风险高 | 注册 expected schema，dry-run preview 通过后才允许 `--execute`。 |
