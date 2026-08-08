# Feature: FBA Inventory Snapshot Ingestion

> 文档状态：Implemented v1.1; Azure verification pending  
> 负责人：AI / 待定  
> 更新时间：2026-08-08  
> 功能状态：Implemented  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关 ADR：`docs/adr/ADR-013-schema-guard-compatibility-policy.md`

---

## 1. 功能摘要

本功能负责把 SP-API Reports 的 `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` 本地 raw flat file 转换为 Azure SQL 的 `dbo.amazon_inventory_daily` 库存快照表。它是 Listing 入库之后的下一条 SP-API normalized ingestion 主线，用于支持运营层面的可售库存、不可售库存、预留库存、入库中库存和库存异常解释。

本功能第一版只做本地已下载 raw report 的解析、schema guard、dry-run preview、Azure SQL MERGE/upsert 和幂等性验证；不负责自动提交/下载 report，也不负责库存周转、补货建议、库龄费用或利润报表计算。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 数据源取样 | 已完成 |
| Parser | 已实现，复用 `FbaInventoryParser` |
| Dry-run preview | 已实现并用真实 raw file 验证 |
| Schema guard | v1.1 robustness 已实现：additive drift non-blocking，required raw contract=`sku` + `afn-fulfillable-quantity`；Azure 重跑待验证 |
| Repository/upsert | 已实现并通过用户本地 Azure SQL execute 验证 |
| 004 migration | 已执行成功，3/3 batches |
| Azure SQL execute | 已完成，首次 inserted=5、updated=0 |
| 幂等性验证 | 已完成，第二次 inserted=0、updated=5 |
| 单元测试 | 已新增并通过 |
| 文档同步 | 已同步 004 执行状态、代码路径、dry-run、execute 和幂等性结果 |

功能整体状态：`Implemented`。当前已完成 004 migration、mapping、dry-run、schema guard、repository、专用 CLI、真实 Azure SQL `--execute` 和第二次幂等性验证。

## 3. 业务目标

库存是当前电商运营和清仓判断的基础数据之一。本功能目标是让系统每天或每次取样后能够知道每个 SKU/ASIN/FNSKU 在 FBA 的库存状态，尤其是：

1. 当前 FBA 可售库存，即 `afn-fulfillable-quantity`。
2. 仓库总库存，即 `afn-warehouse-quantity` / `afn-total-quantity`。
3. 不可售库存，即 `afn-unsellable-quantity`。
4. 已预留库存，即 `afn-reserved-quantity`。
5. 入库中库存，即 working / shipped / receiving。
6. researching / future supply 等异常或未来供给字段。

后续功能会基于本表和 Sales & Traffic / Settlement / Ads 数据结合，计算库存周转、缺货风险、清仓速度、补货建议和现金回收判断。但这些后续分析不属于本功能第一版。

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` raw flat file。
- 使用统一 flat file 解码和 delimiter 探测逻辑。
- 对当前观察到的 22 个源字段做 expected schema 检查。
- 把源字段映射为 `InventoryDailyRecord` / DB-ready rows。
- 生成 dry-run preview JSONL。
- 默认 dry-run，不写数据库。
- 显式 `--execute` 时写入 `dbo.amazon_inventory_daily`。
- 写入 `amazon_sync_run_log` 和 `amazon_schema_validation_event`。
- 支持重复 execute 幂等性验证。
- 保留完整 `raw_data` 和 `source_row_hash` 便于追溯。

### 4.2 本功能不包含

- 不负责提交/下载 SP-API report request。
- 不负责 Listing 状态、标题、价格等主数据；这些来自 `feature_listing_snapshot_ingestion.md`。
- 不负责库存流水事件；这些应由 `GET_LEDGER_SUMMARY_VIEW_DATA` / `GET_LEDGER_DETAIL_VIEW_DATA` 功能处理。
- 不负责库龄、补货推荐、低库存费、AIS 费用等库存规划字段；这些应由库存规划/补货功能处理。
- 不负责订单、销售、结算、广告、利润核算或周报生成。
- 不负责自动调库存、自动调价或自动补货。
- 不负责 Azure Container Apps Jobs 定时化；第一版先完成本地 CLI + Azure SQL 写库闭环。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | tab-delimited flat file | 已取样，5 行，22 列 | 已完成 parser / dry-run / repository / execute | FBA SKU 库存快照。 |

当前样例记录：

| 项目 | 当前值 |
|---|---|
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA/2026-05-14/112429020587.txt` |
| encoding | `cp1252` |
| delimiter | tab |
| row_count | `5` |
| column_count | `22` |
| sample doc | `requirements_to_be_deprecated/data_samples/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA.md` |

当前 raw 路径约定：

```text
reports/raw/amazon/{marketplace_id}/{report_type}/{date}/{report_id}.txt
```

## 6. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/sp_api/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA/{marketplace_id}/{timestamp}/...` | 本次 dry-run / execute 汇总。 |
| Schema events JSONL | `runtime/ingestion/sp_api/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA/{marketplace_id}/{timestamp}/schema_validation_events.jsonl` | 入库前字段验证结果。 |
| Preview rows | `runtime/ingestion/sp_api/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA/{marketplace_id}/{timestamp}/previews/*.preview.jsonl` | DB-ready preview，不加 `--execute` 时只生成这些文件。 |
| Azure SQL table | `dbo.amazon_inventory_daily` | FBA SKU 库存日快照。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录本 report 的 schema guard 结果。 |

## 7. 处理流程

按 Listing 入库的专用入口模式实现，不急于抽象通用 SP-API ingestion 入口：

```text
local raw SP-API inventory flat file
  -> find latest raw file for marketplace/report_type, or accept --raw-file explicit path
  -> decode content and detect delimiter
  -> analyze observed fields
  -> compare with expected inventory schema
  -> if requires_review=True: block database write
  -> parse raw rows into InventoryDailyRecord
  -> compute source_row_hash
  -> compute business_key_hash
  -> write DB-ready preview JSONL
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE preview rows into amazon_inventory_daily by business_key_hash
  -> insert schema validation event
  -> update amazon_sync_run_log final status
  -> commit transaction
```

关键行为：

1. 默认模式必须是 dry-run，不写数据库。
2. 只有显式传入 `--execute` 才允许连接 Azure SQL 并写库。
3. 如果 schema guard 产生 `requires_review=True`，真实写库必须被阻断。
4. 写库必须通过 `get_connection()`，让 Azure SQL connection retry + `SELECT 1` warm-up 先完成。
5. 写库时先创建 running 状态的 sync run，再 upsert，最后更新 success/failed。
6. 如果 upsert 阶段异常，应 rollback，并尽量写失败审计。
7. 本功能不能直接使用 `source_row_hash` 作为业务幂等键；应使用业务键或 `business_key_hash`。

## 8. 字段映射

### 8.1 源字段到标准字段

| 源字段 | 标准字段 | 类型 | 是否必需 | 当前处理 | 说明 |
|---|---|---|---|---|---|
| `sku` | `seller_sku` | string | yes | mapped | 卖家 SKU。 |
| `fnsku` | `fnsku` | string | yes for current sample | mapped | FBA FNSKU。 |
| `asin` | `asin` | string | yes for current sample | mapped | Amazon ASIN。 |
| `product-name` | `product_name` | string | yes for current sample | mapped | 商品标题/名称。 |
| `condition` | `condition` | string | yes for current sample | mapped | 当前样例为 `New`。 |
| `your-price` | `your_price` | decimal | yes for current sample | mapped | 当前样例非空；非法 decimal 应阻断。 |
| report/default | `currency` | string | no | derived | 当前可默认 `USD`，后续可从 marketplace metadata 获取。 |
| `mfn-listing-exists` | `mfn_listing_exists` | boolean | yes for current sample | mapped | `Yes/No` -> bit。 |
| `mfn-fulfillable-quantity` | `mfn_fulfillable_quantity` | int | no | mapped | 当前样例为空；保留字段。 |
| `afn-listing-exists` | `afn_listing_exists` | boolean | yes for current sample | mapped | `Yes/No` -> bit。 |
| `afn-warehouse-quantity` | `afn_warehouse_quantity` | int | yes for current sample | mapped | FBA 仓库库存数量。 |
| `afn-fulfillable-quantity` | `afn_fulfillable_quantity` | int | yes for current sample | mapped | 第一版运营可售库存主口径。 |
| `afn-unsellable-quantity` | `afn_unsellable_quantity` | int | yes for current sample | mapped | 不可售库存。 |
| `afn-reserved-quantity` | `afn_reserved_quantity` | int | yes for current sample | mapped | 预留库存。 |
| `afn-total-quantity` | `afn_total_quantity` | int | yes for current sample | mapped | FBA 总库存。 |
| `per-unit-volume` | `per_unit_volume` | decimal | no | mapped | 单位体积；非法 decimal 应阻断。 |
| `afn-inbound-working-quantity` | `afn_inbound_working_quantity` | int | no | mapped | 入库 working 数量。 |
| `afn-inbound-shipped-quantity` | `afn_inbound_shipped_quantity` | int | no | mapped | 入库 shipped 数量。 |
| `afn-inbound-receiving-quantity` | `afn_inbound_receiving_quantity` | int | no | mapped | 入库 receiving 数量。 |
| `afn-researching-quantity` | `afn_researching_quantity` | int | no | mapped | researching 库存。 |
| `afn-reserved-future-supply` | `afn_reserved_future_supply` | int | no | mapped | future supply 相关字段。 |
| `afn-future-supply-buyable` | `afn_future_supply_buyable` | int | no | mapped | future supply 可购买数量。 |
| `store` | `store` | string | no | mapped | 当前样例为空；保留字段。 |
| raw row object | `raw_data` | JSON string | yes | mapped | 完整保留源行。 |

解析规则：

- flat file 使用统一 `decode_report_content` / `detect_report_delimiter` 逻辑。
- 当前样例编码识别为 `cp1252`，不要假设 UTF-8。
- 当前样例为 tab-delimited。
- 空字符串统一转为 `None`。
- int 字段使用严格整数解析；非法 int 应阻断本次入库。
- decimal 字段使用 `Decimal`；非法 decimal 应阻断本次入库。
- boolean 字段支持 `yes/no`、`true/false`、`1/0` 的大小写变体；非预期值应阻断本次入库。
- `raw_data` 必须保存完整源行。

### 8.2 标准字段到数据库字段

| 标准字段 | 目标表 | 目标字段 | 类型 | 转换规则 |
|---|---|---|---|---|
| `marketplace_id` | `dbo.amazon_inventory_daily` | `marketplace_id` | `NVARCHAR(50)` | CLI 参数或 `.env`。 |
| `snapshot_date` | `dbo.amazon_inventory_daily` | `snapshot_date` | `DATE` | CLI 参数、raw file 日期目录或默认处理日期；应在 CLI 中显式支持。 |
| `seller_sku` | `dbo.amazon_inventory_daily` | `seller_sku` | `NVARCHAR(200)` | 来自 `sku`。 |
| `fnsku` | `dbo.amazon_inventory_daily` | `fnsku` | `NVARCHAR(100)` | 来自 `fnsku`。 |
| `asin` | `dbo.amazon_inventory_daily` | `asin` | `NVARCHAR(50)` | 来自 `asin`。 |
| `product_name` | `dbo.amazon_inventory_daily` | `product_name` | `NVARCHAR(1000)` | 来自 `product-name`。 |
| `condition` | `dbo.amazon_inventory_daily` | `condition` | `NVARCHAR(50)` | 来自 `condition`。 |
| `your_price` | `dbo.amazon_inventory_daily` | `your_price` | `DECIMAL(18,4)` | 来自 `your-price`。 |
| `currency` | `dbo.amazon_inventory_daily` | `currency` | `NVARCHAR(10)` | 初期使用 marketplace 默认币种，US 为 `USD`。 |
| `mfn_listing_exists` | `dbo.amazon_inventory_daily` | `mfn_listing_exists` | `BIT` | 来自 `mfn-listing-exists`。 |
| `mfn_fulfillable_quantity` | `dbo.amazon_inventory_daily` | `mfn_fulfillable_quantity` | `INT` | 来自 `mfn-fulfillable-quantity`。 |
| `afn_listing_exists` | `dbo.amazon_inventory_daily` | `afn_listing_exists` | `BIT` | 来自 `afn-listing-exists`。 |
| `afn_warehouse_quantity` | `dbo.amazon_inventory_daily` | `afn_warehouse_quantity` | `INT` | 来自 `afn-warehouse-quantity`。 |
| `afn_fulfillable_quantity` | `dbo.amazon_inventory_daily` | `afn_fulfillable_quantity` | `INT` | 来自 `afn-fulfillable-quantity`。 |
| `afn_unsellable_quantity` | `dbo.amazon_inventory_daily` | `afn_unsellable_quantity` | `INT` | 来自 `afn-unsellable-quantity`。 |
| `afn_reserved_quantity` | `dbo.amazon_inventory_daily` | `afn_reserved_quantity` | `INT` | 来自 `afn-reserved-quantity`。 |
| `afn_total_quantity` | `dbo.amazon_inventory_daily` | `afn_total_quantity` | `INT` | 来自 `afn-total-quantity`。 |
| `per_unit_volume` | `dbo.amazon_inventory_daily` | `per_unit_volume` | `DECIMAL(18,6)` | 来自 `per-unit-volume`。 |
| `afn_inbound_working_quantity` | `dbo.amazon_inventory_daily` | `afn_inbound_working_quantity` | `INT` | 来自 `afn-inbound-working-quantity`。 |
| `afn_inbound_shipped_quantity` | `dbo.amazon_inventory_daily` | `afn_inbound_shipped_quantity` | `INT` | 来自 `afn-inbound-shipped-quantity`。 |
| `afn_inbound_receiving_quantity` | `dbo.amazon_inventory_daily` | `afn_inbound_receiving_quantity` | `INT` | 来自 `afn-inbound-receiving-quantity`。 |
| `afn_researching_quantity` | `dbo.amazon_inventory_daily` | `afn_researching_quantity` | `INT` | 来自 `afn-researching-quantity`。 |
| `afn_reserved_future_supply` | `dbo.amazon_inventory_daily` | `afn_reserved_future_supply` | `INT` | 来自 `afn-reserved-future-supply`。 |
| `afn_future_supply_buyable` | `dbo.amazon_inventory_daily` | `afn_future_supply_buyable` | `INT` | 来自 `afn-future-supply-buyable`。 |
| `store` | `dbo.amazon_inventory_daily` | `store` | `NVARCHAR(200)` | 来自 `store`。 |
| `source_system` | `dbo.amazon_inventory_daily` | `source_system` | `NVARCHAR(50)` | 固定 `sp_api_reports`。 |
| `source_report_type` | `dbo.amazon_inventory_daily` | `source_report_type` | `NVARCHAR(120)` | 固定 `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA`。 |
| `source_report_id` | `dbo.amazon_inventory_daily` | `source_report_id` | `NVARCHAR(120)` | Amazon report id；本地 raw file stem 可作为 fallback。 |
| `source_raw_file_path` | `dbo.amazon_inventory_daily` | `source_raw_file_path` | `NVARCHAR(1000)` | 本地 raw file 路径。 |
| `source_run_id` | `dbo.amazon_inventory_daily` | `source_run_id` | `BIGINT` | 对应 `amazon_sync_run_log.id`。 |
| `source_row_hash` | `dbo.amazon_inventory_daily` | `source_row_hash` | `NVARCHAR(100)` | SHA256 canonical raw row。 |
| `business_key_hash` | `dbo.amazon_inventory_daily` | `business_key_hash` | `NVARCHAR(100)` | 需要新增 migration 后写入；SHA256 canonical business key。 |
| `raw_data` | `dbo.amazon_inventory_daily` | `raw_data` | `NVARCHAR(MAX)` | 完整源行 JSON。 |

## 9. 目标数据表设计

### 9.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.amazon_inventory_daily` | yes | FBA SKU 库存快照 | MERGE/upsert 已实现并验证 |
| `dbo.amazon_sync_run_log` | yes | 任务审计 | insert then update |
| `dbo.amazon_schema_validation_event` | yes | schema guard 审计 | append-only insert |
| `dbo.amazon_raw_report_file` | yes | raw file registry | 后续应写入；本功能首版可先保存 path/hash |

### 9.2 业务主键 / 幂等键

建议业务键：

```text
business_key = marketplace_id + snapshot_date + seller_sku + fnsku + asin
business_key_hash = sha256(canonical JSON of business_key)
```

说明：

- `seller_sku` 是本功能最核心业务键。
- `fnsku` 能区分 FBA 维度库存。
- `asin` 便于补充追溯，但如果未来出现空值，business key 计算应稳定处理空值。
- `snapshot_date` 必须参与业务键，否则同一 SKU 的每日库存会互相覆盖。
- 不使用 `source_row_hash` 作为业务键，因为同一 SKU 同一天重新下载后指标可能变化，业务上应 update 而不是 insert 新行。

### 9.3 新 migration 需求

当前 `dbo.amazon_inventory_daily` 表已存在，但根据当前 repository/upsert 标准，仍建议新增 `business_key_hash` 和唯一过滤索引，保持与 Ads / Listing 的幂等模式一致。

| 变化 | 原因 | migration 文件 | 状态 |
|---|---|---|---|
| 新增 `amazon_inventory_daily.business_key_hash NVARCHAR(100) NULL` | 支持稳定 MERGE/upsert 幂等键，避免长组合唯一索引问题 | `004_add_inventory_daily_business_key_hash.sql` | executed, 3/3 batches |
| 新增唯一过滤索引 `UX_amazon_inventory_daily_business_key_hash` | 防止同一业务键重复插入 | `004_add_inventory_daily_business_key_hash.sql` | executed, 3/3 batches |

`sql/migrations/004_add_inventory_daily_business_key_hash.sql` 已按 Listing 的 `003_add_listing_snapshot_business_key_hash.sql` 模式执行成功：先检查 `dbo.amazon_inventory_daily` 是否存在，再新增 nullable `business_key_hash`，最后创建唯一过滤索引。用户本地已运行 `scripts/export_database_schema_spec.py --output-prefix after_004_inventory_business_key --include-row-counts`，并已据 live schema 更新 `docs/database/database_current_schema_spec.md`。后续结构变化必须新增 `005_xxx.sql`，不得回改 `001/002/003/004`。

## 10. 幂等性设计

重复执行同一批 Inventory raw file 应该安全。

已完成验收：

```text
Dry-run: prepared_rows=5 requires_review=False
第一次 execute: sync_run_id=5 attempted=5 inserted=5 updated=0 written=5 skipped=0
第二次 execute: sync_run_id=6 attempted=5 inserted=0 updated=5 written=5 skipped=0
目标表总行数保持 5
```

如果后续 repository 增加“完全相同内容不更新”的优化，也可以接受：

```text
第二次 execute: inserted=0 updated=0 skipped=5
```

但绝对不应第二次再次 `inserted=5`。

## 11. Schema guard 与异常处理

| 场景 | 处理方式 | 是否阻塞入库 | 是否记录 validation event |
|---|---|---|---|
| 缺少必需字段，例如 `sku` | `requires_review=True` | yes | yes |
| 出现新增字段 | 记录 `new_fields` warning；继续按原 mapping 入库，未知字段保留在 raw data | no | yes |
| 空文件但有 header | 允许 dry-run，execute 写 0 行；状态可为 warning | no | yes |
| 数字解析失败 | 记录错误并阻断 execute | yes | yes |
| boolean 解析失败 | 记录错误并阻断 execute | yes | yes |
| 编码或 delimiter 识别失败 | 阻断 dry-run/execute | yes | yes if possible |

第一版 expected schema 曾覆盖当前 22 个 observed source fields。2026-08-08 起按 `feature_schema_guard_resilience.md` / ADR-013 修订：`expected_fields` 用于 drift 观测，`required_fields` 只保留最小核心契约；新增字段不再阻断。

### 11.1 2026-08-08 schema guard robustness v1.1 实现

2026-08-03 真实自动化运行新增：

```text
afn-fc-transfer-quantity
afn-onhand-buyable-quantity
```

同时 `missing_fields=[]`。旧策略仍返回 `requires_review=True` 并阻断库存快照，导致后续报告持续看到 2026-06-22 的 stale inventory snapshot。该行为已确认属于 false-positive blocking。

v1.1 required raw contract 已实现为：

```text
sku
afn-fulfillable-quantity
```

其他已知字段继续尽量解析和写入；单个非关键字段整体缺失不应停止全部 inventory snapshot。关键整数/布尔/编码解析失败仍阻断。

## 12. 审计与可追溯性

| 审计对象 | 表/字段 | 说明 |
|---|---|---|
| 任务运行 | `amazon_sync_run_log` | `job_name`, `workflow_name`, `status`, `rows_read`, `rows_written`, `rows_skipped`, `rows_failed`, `message`。 |
| Schema validation | `amazon_schema_validation_event` | `observed_fields_json`, `expected_fields_json`, `missing_fields_json`, `new_fields_json`, `requires_review`。 |
| 源文件路径 | normalized table `source_raw_file_path` | 首版先保存路径，后续补 `source_raw_file_id` 外键。 |
| 源行 | `source_row_hash`, `raw_data` | 支持重放和排查。 |
| 本次运行 | `source_run_id` | 对应 `amazon_sync_run_log.id`。 |

## 13. 建议 CLI

建议新增专用入口：

```powershell
python scripts/ingest_inventory_snapshot.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_inventory_snapshot.py --marketplace-id ATVPDKIKX0DER --execute
```

可选参数：

```powershell
--raw-file <path>
--snapshot-date YYYY-MM-DD
--output-dir runtime/ingestion/sp_api/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA/...
```

说明：按照 `ADR-005-progressive-generalization.md`，当前仍采用专用入口，不急于做通用 `ingest_sp_api_reports.py`。

## 14. 相关代码路径

已新增或复用：

| 路径 | 用途 |
|---|---|
| `scripts/ingest_inventory_snapshot.py` | Inventory 专用 CLI，已新增。 |
| `src/seller_data_pipeline/ingestion/inventory_table_mapping.py` | 字段映射、expected schema、DB row 生成，已新增。 |
| `src/seller_data_pipeline/ingestion/inventory_ingestion_dry_run.py` | dry-run preview 与 schema guard，已新增。 |
| `src/seller_data_pipeline/ingestion/inventory_ingestion.py` | execute orchestration，已新增。 |
| `src/seller_data_pipeline/db/repositories/inventory_repo.py` | Azure SQL MERGE/upsert repository，已新增。 |
| `tests/unit/ingestion/test_inventory_table_mapping.py` | 字段映射测试，已新增。 |
| `tests/unit/ingestion/test_inventory_ingestion_dry_run.py` | dry-run 测试，已新增。 |
| `tests/unit/ingestion/test_inventory_ingestion.py` | execute orchestration 测试，已新增。 |
| `tests/unit/db/test_inventory_repo.py` | repository SQL/upsert 行为测试，已新增。 |

## 15. 验收标准

### 15.1 设计验收

- 本文档完成并进入 `docs/features/README.md` 索引。
- `004_add_inventory_daily_business_key_hash.sql` 已执行成功：3/3 batches。
- 已运行 `scripts/export_database_schema_spec.py --output-prefix after_004_inventory_business_key --include-row-counts` 并据真实结果更新 `docs/database/database_current_schema_spec.md`。

### 15.2 代码验收

- `python scripts/ingest_inventory_snapshot.py --marketplace-id ATVPDKIKX0DER` dry-run 成功。
- dry-run 输出 `prepared_rows=5`，`requires_review=False`。
- `--execute` 首次写入成功。
- 第二次 `--execute` 幂等性通过。
- `amazon_inventory_daily` 行数与 expected rows 一致。
- `amazon_sync_run_log` 有成功记录。
- `amazon_schema_validation_event` 有 `validation_status=ok` 记录。
- `pytest` 通过。
- `compileall` 通过。
- 本功能文档、progress 文档、数据库 spec 同步完成。

## 16. 当前限制与后续优化

1. 2026-08-03 已观察到 Amazon 新增 `afn-fc-transfer-quantity`、`afn-onhand-buyable-quantity`；v1.1 已按 ADR-013 作为 non-blocking additive drift，并保留于 raw data / validation event。
2. 当前不区分多仓库/FC 维度；该 report 是 SKU/FNSKU 聚合库存快照，不是仓库事件明细。
3. 当前不计算库存周转、缺货天数、清仓速度；这些应进入独立分析功能。
4. 当前不写 `amazon_raw_report_file` 外键；后续应补充 raw registry。
5. 当前 `currency` 建议先使用 marketplace 默认值，后续可接 `amazon_marketplace` 维表。

## 17. 弃置记录

| 日期 | 方案 | 处理 | 原因 |
|---|---|---|---|
| 2026-05-17 | 直接做通用 `ingest_sp_api_reports.py` | 暂缓 | 按渐进式抽象规则，先做 Inventory 专用入口，等 Listing + Inventory + Sales & Traffic 至少两到三条链路稳定后再抽象。 |


## 18. 当前实现验证记录

| 日期 | 验证项 | 命令/结果 | 说明 |
|---|---|---|---|
| 2026-05-17 | 004 migration dry-run | `3 executable batches` | 用户本地验证通过。 |
| 2026-05-17 | 004 migration execute | `executed_batches=3/3` | `amazon_inventory_daily.business_key_hash` 与唯一过滤索引已进入真实 Azure SQL。 |
| 2026-05-17 | Live schema export | `after_004_inventory_business_key.md/json` | 用于同步 current schema spec。 |
| 2026-05-17 | Inventory dry-run | `prepared_rows=5 requires_review=False` | 当前真实 raw file 可生成 DB-ready preview。 |
| 2026-05-17 | Inventory first execute | `sync_run_id=5 attempted=5 inserted=5 updated=0 written=5 skipped=0` | 首次真实写库成功。 |
| 2026-05-17 | Inventory idempotency execute | `sync_run_id=6 attempted=5 inserted=0 updated=5 written=5 skipped=0` | 重复执行未重复插入，幂等性通过。 |
| 2026-05-17 | Unit tests | `135 passed` | 新增 Inventory mapping/dry-run/repository/orchestration 测试。 |
| 2026-08-08 | v1.1 additive drift 回归 | 新增两个 2026-08-03 字段后 `status=new_fields`, `requires_review=False`, `prepared_rows=1` | 未新增 SQL column，raw data 完整保留。 |
| 2026-08-08 | v1.1 minimal contract 回归 | 只有 `sku` + `afn-fulfillable-quantity` 仍可正常解析；缺 `sku` 则阻断 | optional columns 不再导致全量停写。 |
| 2026-08-08 | Full tests / compileall | `313 passed`; compileall success | Azure Job 验收待部署新镜像后执行。 |

## 19. 后续维护说明

Inventory 当前首版入库闭环已完成。后续 `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` 出现**新增字段**时，按 ADR-013 记录 drift 但不中断现有字段入库；只有 required contract 缺失或语义/解析错误才阻断。只有新字段有明确结构化业务价值时才另开 feature/migration；不要回改 `001/002/003/004`。
