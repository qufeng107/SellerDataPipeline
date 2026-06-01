# Feature: Orders Report Ingestion

> 文档状态：Implemented; 007 migration, dry-run, execute and idempotency verified  
> 负责人：AI / 待定  
> 更新时间：2026-05-17  
> 功能状态：Implemented  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`

---

## 1. 功能摘要

本功能负责把 SP-API Reports 的 `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` 订单行项目 flat file 转换为 Azure SQL 中的 normalized 订单明细表：

```text
GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL
  -> dbo.amazon_order_item
```

Orders 数据是利润核算和运营分析的重要辅助事实表。Settlement 是财务入账口径，Sales & Traffic 是汇总销售/流量口径，Orders 则提供订单/SKU 行项目、订单状态、发货方式、订单地区、促销折扣和订单金额等维度。第一版只做可靠入库和保守字段映射，不直接计算最终利润。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 数据源取样 | 已完成，1 份 raw file，112 行，33 个源字段 |
| 目标表 | 已存在于 `001_create_core_tables.sql`：`dbo.amazon_order_item`；007 已执行并补充幂等键 |
| Parser | 已存在：`src/seller_data_pipeline/parsers/amazon/orders_report_parser.py` |
| Dry-run preview | 已开发并通过真实 raw file dry-run，prepared_rows=112 |
| Schema guard | 已开发；包含 required fields 校验与 `cpf` 非空 privacy guard |
| Repository/upsert | 已开发并通过 Azure SQL execute 验证 |
| Azure SQL execute | 已完成；首次 execute `sync_run_id=11`，inserted=112，updated=0 |
| 幂等性验证 | 已完成；第二次 execute `sync_run_id=12`，inserted=0，updated=112 |
| 单元测试 | 已新增并通过 |
| 文档同步 | 本设计已完成第一版 |

功能整体状态：`Implemented`。`007_add_order_item_business_key.sql` 已在 Azure SQL 执行成功并导出 `after_007_order_item_business_key` live schema；Orders 专用 dry-run / schema guard / preview / repository / CLI 已开发完成，并已通过真实 raw file dry-run、首次 execute 和第二次 execute 幂等性验证。

## 2.1 验收证据

用户本地已完成以下验收：

```text
Dry-run:
prepared_rows=112 requires_review=False sync_run_id=None

首次 execute:
sync_run_id=11
upsert attempted=112 inserted=112 updated=0 written=112 skipped=0
amazon_order_item: attempted=112 inserted=112 updated=0 skipped=0

第二次 execute:
sync_run_id=12
upsert attempted=112 inserted=0 updated=112 written=112 skipped=0
amazon_order_item: attempted=112 inserted=0 updated=112 skipped=0
```

结论：Orders 入库链路已完成 schema guard、dry-run、真实写库和幂等性验证。

## 3. 业务目标

本功能目标是沉淀订单/SKU 行项目事实，用于后续：

1. 按订单和 SKU 查看销售数量、订单状态、履约渠道、订单金额、税费和运费。
2. 为 Settlement 金额拆解提供订单维度补充，帮助对账和异常排查。
3. 为库存出库、区域销售、B2B 订单、取消订单和发货方式分析提供基础数据。
4. 为利润核算、周报/月报、清仓分析提供订单数量和订单状态维度。

Orders 数据本身不是最终利润口径。后续利润计算必须以 Settlement、Ads、SKU cost、FBA fee、Reimbursements 等多源数据综合计算。

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` raw flat file。
- 校验当前观察到的源字段，以及入库所需 required fields。2026-05-28 云端 collect_ingest 观察到 Amazon 新增返回 `order-item-id`，已将其纳入允许的 raw schema。
- 解析订单行项目字段：订单 id、日期、状态、SKU/ASIN、数量、金额、税、运费、促销折扣、履约方式、销售渠道、发货国家/州/邮编等。
- 生成 `source_row_index`、`source_row_hash` 和 `business_key_hash`。
- 生成 DB-ready preview JSONL。
- 默认 dry-run，不写数据库。
- 显式 `--execute` 时写入 Azure SQL。
- 写入 `amazon_sync_run_log` 和 `amazon_schema_validation_event`。
- 支持重复 execute 幂等性验证。

### 4.2 本功能不包含

- 不主动重新设计订单表结构的大字段集合；第一版复用现有 `amazon_order_item`。
- 不把订单金额直接作为最终利润收入；财务口径以后以 Settlement 为主。
- 不做最终广告归因、SKU 成本分摊、头程分摊或利润计算。
- 不处理退货 report；退货后续应单独设计 `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE`。
- 不处理买家姓名、详细地址、电话、邮箱等高敏信息；当前样例没有这些字段。
- 不把 `cpf` 结构化入库；若未来 `cpf` 非空，第一版应触发 `requires_review=True`，避免把敏感税号静默写入 normalized 表或 raw_data。
- 不做 Azure Container Apps Jobs 定时化。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | tab-delimited flat file | 已取样 1 份，112 行 | parser / ingestion / upsert 已实现并验证 | 订单行项目级别报告，当前通过 order date 维度取样。 |

当前样例：

| 项目 | 当前值 |
|---|---|
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL/2026-05-14/112467020587.txt` |
| row_count | `112` |
| field_path_count | `34` after 2026-05-28 cloud run (`order-item-id` observed); older sample doc may still show 33 |
| delimiter | tab |
| sample doc | `requirements_to_be_deprecated/data_samples/GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL.md` |

## 6. 源字段结构

当前观察到的源字段。2026-05-28 云端 weekly collect_ingest 中，Amazon All Orders raw file 在原有字段之外新增了 `order-item-id`：

```text
amazon-order-id
merchant-order-id
purchase-date
last-updated-date
order-status
order-item-id
fulfillment-channel
sales-channel
order-channel
ship-service-level
product-name
sku
asin
item-status
quantity
currency
item-price
item-tax
shipping-price
shipping-tax
gift-wrap-price
gift-wrap-tax
item-promotion-discount
ship-promotion-discount
ship-city
ship-state
ship-postal-code
ship-country
promotion-ids
cpf
is-business-order
purchase-order-number
price-designation
signature-confirmation-recommended
```

`order-item-id` 当前只作为已知 raw field 接受并保留在 `raw_data` 中，暂不新增数据库列，也暂不改变既有 `business_key_hash` 算法，避免与已入库历史订单产生幂等键不兼容。后续如果确认它长期稳定，可另行设计 migration/业务键版本。

第一版 required fields 应以现有 parser 的 `ALL_ORDERS_REQUIRED_FIELDS` 为基础，但需要新增 privacy guard：如果 `cpf` 非空，应设置 `requires_review=True` 并阻断 execute，直到明确是否要丢弃、脱敏或单独加密保存。

## 7. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/sp_api/GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL/{marketplace_id}/{timestamp}/...` | 本次 dry-run / execute 汇总。 |
| Schema events JSONL | 同上 | 入库前字段验证结果。 |
| Preview rows | `previews/amazon_order_item.preview.jsonl` | Orders DB-ready preview。 |
| Azure SQL table | `dbo.amazon_order_item` | 订单/SKU 行项目事实表。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录本 report 的 schema guard 结果。 |

## 8. 处理流程

按已验证的专用入口模式实现：

```text
local orders raw file
  -> find latest raw file for marketplace/report_type, or accept --raw-file explicit path
  -> decode flat file and detect delimiter
  -> validate required order fields
  -> apply privacy guard for cpf and other unexpected sensitive fields
  -> parse rows with AllOrdersReportParser
  -> compute source_row_index per raw file
  -> compute source_row_hash for each raw row
  -> compute business_key_hash for each target row
  -> detect duplicate business keys within the same batch
  -> write DB-ready preview JSONL
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE rows into amazon_order_item by business_key_hash
  -> insert schema validation event(s)
  -> update amazon_sync_run_log final status
  -> commit transaction
```

关键行为：

1. 默认 dry-run，不写数据库。
2. 只有显式 `--execute` 才允许写 Azure SQL。
3. `requires_review=True` 时必须阻断 execute。
4. 写库必须通过 `get_connection()`，让 Azure SQL connection retry + `SELECT 1` warm-up 生效。
5. 同一 raw file 内如果出现重复 business key 且源行内容不同，必须 requires_review 并阻断 execute，避免误覆盖。

## 9. 字段映射

### 9.1 源字段到标准字段

| 源字段 | 标准字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|---|
| `amazon-order-id` | `amazon_order_id` | string | yes | Amazon order id。 |
| `merchant-order-id` | `merchant_order_id` | string | no | Merchant order id。 |
| `purchase-date` | `purchase_date_raw` | string | yes | 原样保存 ISO datetime string。 |
| `last-updated-date` | `last_updated_date_raw` | string | yes | 原样保存 ISO datetime string。 |
| `order-status` | `order_status` | string | yes | Cancelled / Shipping / Shipped / Pending 等。 |
| `order-item-id` | not structured | string | no | 2026-05-28 云端样例观察到的订单行 id；当前保留在 `raw_data`，不结构化入库、不参与既有 business key。 |
| `fulfillment-channel` | `fulfillment_channel` | string | yes | 样例为 Amazon。 |
| `sales-channel` | `sales_channel` | string | yes | Amazon.com / Non-Amazon。 |
| `order-channel` | `order_channel` | string | no | 当前样例为空。 |
| `ship-service-level` | `ship_service_level` | string | no | Standard / Expedited / SecondDay。 |
| `product-name` | `product_name` | string | yes | 商品名。 |
| `sku` | `seller_sku` | string | yes | 卖家 SKU。 |
| `asin` | `asin` | string | yes | ASIN。 |
| `item-status` | `item_status` | string | yes | Shipped / Unshipped / Cancelled。 |
| `quantity` | `quantity` | int | yes | 订单行数量。 |
| `currency` | `currency` | string | yes for non-cancelled monetary rows | 币种。 |
| `item-price` | `item_price` | decimal | no | 商品金额。 |
| `item-tax` | `item_tax` | decimal | no | 商品税。 |
| `shipping-price` | `shipping_price` | decimal | no | 运费。 |
| `shipping-tax` | `shipping_tax` | decimal | no | 运费税。 |
| `gift-wrap-price` | `gift_wrap_price` | decimal | no | 礼品包装费。 |
| `gift-wrap-tax` | `gift_wrap_tax` | decimal | no | 礼品包装税。 |
| `item-promotion-discount` | `item_promotion_discount` | decimal | no | 商品促销折扣。 |
| `ship-promotion-discount` | `ship_promotion_discount` | decimal | no | 运费促销折扣。 |
| `ship-city` | `ship_city` | string | no | 低粒度发货城市；注意隐私。 |
| `ship-state` | `ship_state` | string | no | 州/地区。 |
| `ship-postal-code` | `ship_postal_code` | string | no | 邮编；注意隐私和导出限制。 |
| `ship-country` | `ship_country` | string | no | 国家/地区。 |
| `promotion-ids` | `promotion_ids` | string | no | 促销 id。 |
| `cpf` | not mapped | string | no | 不结构化入库；非空时 first version requires_review=True。 |
| `is-business-order` | `is_business_order` | bool | yes | B2B 订单标记。 |
| `purchase-order-number` | `purchase_order_number` | string | no | B2B purchase order number。 |
| `price-designation` | `price_designation` | string | no | 价格标识。 |
| `signature-confirmation-recommended` | `signature_confirmation_recommended` | bool | no | 签收确认建议。 |

### 9.2 标准字段到数据库字段

目标表 `dbo.amazon_order_item` 已包含以上主要字段。第一版额外需要通过 007 新增：

| 标准字段 | 目标表 | 目标字段 | 类型 | 转换规则 |
|---|---|---|---|---|
| computed row index | `dbo.amazon_order_item` | `source_row_index` | INT | raw file 内 1-based data row index。 |
| computed business key | `dbo.amazon_order_item` | `business_key_hash` | NVARCHAR(100) | 对 canonical business key 做 sha256。 |

`raw_data` 当前会保存源行 JSON。因 order report 包含地址相关字段和 `cpf` 字段，第一版应至少对 `cpf` 非空做阻断；后续可评估 raw_data 脱敏策略。

## 10. 目标数据表设计

### 10.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.amazon_order_item` | yes | 订单/SKU 行项目明细。 | MERGE/upsert |
| `dbo.amazon_sync_run_log` | yes | 任务级审计。 | insert/update |
| `dbo.amazon_schema_validation_event` | yes | schema guard 记录。 | insert |

### 10.2 业务主键 / 幂等键

首版建议：

```text
business_key = marketplace_id
             + source_report_type
             + amazon_order_id
             + seller_sku
             + asin
             + purchase_date_raw
```

理由：

1. `amazon-order-id` 是订单主键。
2. 历史取样阶段没有稳定 `order-item-id` 字段，因此既有入库键使用 SKU/ASIN 共同限定订单行；2026-05-28 云端样例开始观察到 `order-item-id`，但为避免改变历史幂等键，当前仅接受并保存在 `raw_data`。
3. `purchase-date` 增加防冲突能力。
4. `order-status` / `item-status` 不进入 business key，这样同一订单行状态变化时应 update，而不是插入新行。

风险：如果同一订单中同一 SKU/ASIN 被拆成多条完全独立行，可能发生 business key 冲突。第一版应在 dry-run 内检测重复 business key；如果重复 key 对应不同 raw row，阻断 execute 并人工确认是否要把 `source_row_index` 或其他字段纳入 key。

### 10.3 新 migration 需求

| 变化 | 原因 | migration 文件 | 状态 |
|---|---|---|---|
| 新增 `source_row_index INT NULL` | 源文件行级追溯和冲突排查。 | `007_add_order_item_business_key.sql` | executed, 4/4 batches |
| 新增 `business_key_hash NVARCHAR(100) NULL` | 支持稳定 MERGE/upsert 幂等。 | `007_add_order_item_business_key.sql` | executed, 4/4 batches |
| 新增唯一过滤索引 `UX_amazon_order_item_business_key_hash` | 防止重复插入同一订单行。 | `007_add_order_item_business_key.sql` | executed, 4/4 batches |

007 已执行成功，且 `docs/database/database_current_schema_spec.md` 已根据 `after_007_order_item_business_key` live schema 记录 `source_row_index`、`business_key_hash` 和唯一过滤索引。后续结构变化必须从 `008_xxx.sql` 开始。

## 11. 幂等性设计

重复执行同一批 Orders 数据必须安全：

```text
第一次 execute:
  attempted=112 inserted=112 updated=0

第二次 execute:
  attempted=112 inserted=0 updated=112
```

如果后续 repository 增加“完全相同内容不更新”的优化，也可以接受第二次 `updated=0 skipped=112`，但绝对不应重复插入 112 行。

## 12. Schema guard 与异常处理

| 场景 | 处理方式 | 是否阻塞入库 | 是否记录 validation event |
|---|---|---|---|
| 缺少 required fields | 阻断 | yes | yes |
| 出现新增字段 | 未登记字段记录 warning 并 requires_review；已登记但暂不结构化的字段如 `order-item-id` 不阻断，保留在 `raw_data` | conditional | yes |
| `cpf` 非空 | requires_review=True，阻断 execute | yes | yes |
| decimal/int/bool 解析失败 | 阻断 execute | yes | yes |
| 日期字段为空或格式异常 | required 字段为空时阻断；格式异常先保留 raw string 并 warning | conditional | yes |
| 空文件 | dry-run 显示 prepared_rows=0，execute no-op 或阻断，需明确记录 | yes/no-op | yes |
| 同批重复 business key 且 raw row 不一致 | requires_review=True，阻断 execute | yes | yes |

## 13. 审计与可追溯性

| 审计对象 | 表/字段 | 说明 |
|---|---|---|
| 任务级审计 | `amazon_sync_run_log` | source_system=`sp_api_reports`，job_name 可用 `ingest_orders_report`。 |
| schema guard | `amazon_schema_validation_event` | 记录字段验证、privacy guard 和 requires_review。 |
| 原始文件路径 | `source_raw_file_path` | 当前先记录路径，后续补 raw file registry 外键。 |
| 原始报告 id | `source_report_id` | 可从文件名提取，例如 `112467020587`。 |
| 源行 hash | `source_row_hash` | 用于追溯源行内容。 |
| 源行序号 | `source_row_index` | 007 新增后用于定位 raw file 内行号。 |
| 原始行 | `raw_data` | 保存源行 JSON；需注意 `cpf`/地址字段隐私。 |

## 14. 命令行入口

建议新增：

```powershell
python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER --execute
```

可选参数：

```text
--raw-file <path>      # 指定单个 raw file；不传则默认找该 marketplace/report_type 下最新 raw file
--output-dir <path>
```

说明：按照 `ADR-005-progressive-generalization.md`，当前仍采用专用入口，不急于做通用 `ingest_sp_api_reports.py`。

## 15. 相关代码路径

已有：

| 路径 | 用途 |
|---|---|
| `src/seller_data_pipeline/parsers/amazon/orders_report_parser.py` | 已有 All Orders parser、required fields 和基础类型转换。 |
| `requirements_to_be_deprecated/data_samples/GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL.md` | 当前 Orders 取样记录。 |

建议新增：

| 路径 | 用途 |
|---|---|
| `scripts/ingest_orders_report.py` | Orders 专用 CLI。 |
| `src/seller_data_pipeline/ingestion/orders_table_mapping.py` | 字段映射、expected schema、business_key_hash 生成。 |
| `src/seller_data_pipeline/ingestion/orders_ingestion_dry_run.py` | dry-run preview 与 schema guard。 |
| `src/seller_data_pipeline/ingestion/orders_ingestion.py` | execute orchestration。 |
| `src/seller_data_pipeline/db/repositories/orders_repo.py` | Azure SQL MERGE/upsert repository。 |
| `tests/unit/ingestion/test_orders_table_mapping.py` | 字段映射测试。 |
| `tests/unit/ingestion/test_orders_ingestion_dry_run.py` | dry-run 测试。 |
| `tests/unit/db/test_orders_repo.py` | repository SQL/upsert 行为测试。 |

## 16. 测试计划

```bash
PYTHONPATH=src pytest -q tests/unit/ingestion/test_orders_table_mapping.py
PYTHONPATH=src pytest -q tests/unit/ingestion/test_orders_ingestion_dry_run.py
PYTHONPATH=src pytest -q tests/unit/db/test_orders_repo.py
PYTHONPATH=src pytest -q
python -m compileall -q scripts src tests
```

真实 Azure SQL 手工验收：

```powershell
python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER --execute
python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER --execute
```

## 17. 验收标准

### 17.1 设计与数据库验收

- 本文档完成并进入 `docs/features/README.md` 索引。
- `007_add_order_item_business_key.sql` 已创建。
- 007 dry-run 应显示 `4 executable batches`。
- 007 在 Azure SQL 执行成功。
- 已运行 `scripts/export_database_schema_spec.py --output-prefix after_007_order_item_business_key --include-row-counts`。
- `docs/database/database_current_schema_spec.md` 已据真实 schema 更新 `source_row_index`、`business_key_hash` 和唯一过滤索引。

### 17.2 代码验收

- `python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER` dry-run 成功。
- dry-run 输出合计 `prepared_rows=112`、`requires_review=False`，或明确说明 privacy/schema review 原因。
- `--execute` 首次写入成功。
- 第二次 `--execute` 幂等性通过。
- `amazon_order_item` 行数与 expected rows 一致。
- `amazon_sync_run_log` 有成功记录。
- `amazon_schema_validation_event` 有 `validation_status=ok` 或可解释 warning 记录。
- 单元测试通过。
- `compileall` 通过。
- 本功能文档、progress 文档、数据库 spec 同步完成。

## 18. 当前实现状态

| 日期 | 进展 | 证据/命令 | 备注 |
|---|---|---|---|
| 2026-05-17 | 完成 Orders 入库功能设计第一版 | 本文档 | 下一步准备 007 migration。 |
| 2026-05-17 | 准备 `007_add_order_item_business_key.sql` | `python scripts/run_sql_migration.py --file sql/migrations/007_add_order_item_business_key.sql --dry-run --show-batches` -> `4 executable batches` | 已由用户执行。 |
| 2026-05-17 | 执行 007 并导出 live schema | `run_sql_migration.py` -> executed_batches=4/4；`export_database_schema_spec.py --output-prefix after_007_order_item_business_key --include-row-counts` -> success | current schema spec 已同步。 |
| 2026-05-17 | 开发 Orders 专用 ingestion 并完成 dry-run | `python scripts/ingest_orders_report.py --marketplace-id ATVPDKIKX0DER` -> prepared_rows=112 requires_review=False | 已完成。 |
| 2026-05-17 | 完成 Orders 真实 execute 和第二次 execute 幂等性验证 | 首次 `sync_run_id=11` inserted=112 updated=0；第二次 `sync_run_id=12` inserted=0 updated=112 | 功能状态更新为 Implemented。 |

## 19. 后续优化

1. 后续可增加 parsed `purchase_date` / `last_updated_date` 标准 datetime 字段；第一版先保留 raw string。
2. 后续可评估是否只保留州/国家级别地理信息，或对 postal code 做前缀化/脱敏。
3. 后续可把 Orders 与 Settlement 做订单级对账，识别缺失订单、退款差异和促销折扣差异。
4. 后续 raw file registry 完成后，应补 `source_raw_file_id` 外键关联。

## 20. 弃置记录

| 日期 | 弃置内容 | 原因 | 替代方案 |
|---|---|---|---|
| 2026-05-17 | 在 Orders ingestion 中直接计算利润 | Orders 不是财务入账最终口径，利润需要 Settlement/Ads/Cost/Fee 等共同参与。 | 先可靠入库，后续单独设计 `feature_profit_calculation.md`。 |
| 2026-05-17 | 把 `cpf` 结构化入库 | 税号字段敏感，当前样例为空且业务不需要。 | 非空时 requires_review，后续另行决定脱敏/丢弃策略。 |
