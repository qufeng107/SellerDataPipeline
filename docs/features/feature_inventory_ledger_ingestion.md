# Feature: Inventory Ledger Ingestion

> 文档状态：Implementing; 011 executed; dedicated ingestion dry-run implemented  
> 负责人：AI / 待定  
> 更新时间：2026-05-17  
> 功能状态：Implementing  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`

---

## 1. 功能摘要

本功能负责把 FBA Inventory Ledger 库存流水 report 入库，用于库存变化解释、FBA 异常排查、赔偿核对和后续周报中的库存 movement 分析。

目标链路：

```text
GET_LEDGER_SUMMARY_VIEW_DATA
  -> dbo.amazon_inventory_ledger_summary_daily

GET_LEDGER_DETAIL_VIEW_DATA
  -> dbo.amazon_inventory_ledger_detail
```

需要明确：**周报里展示“还剩多少货”不一定依赖 Inventory Ledger**。当前库存余额优先来自 `amazon_inventory_daily`，因为它是库存快照；Inventory Ledger 更适合解释“为什么库存变多/变少”，例如 receipts、customer shipments、returns、found/lost/damaged、warehouse transfers 等。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认；用户希望周报可看剩余库存，也希望保留库存审计能力 |
| 数据源取样 | 已完成；summary 150 行，detail 207 行 |
| 目标表 | 已存在于 `001_create_core_tables.sql`：summary/detail 两张表 |
| Parser | 已存在：`src/seller_data_pipeline/parsers/amazon/inventory_ledger_parser.py` |
| Migration | 已执行：`011_add_inventory_ledger_business_keys.sql`，4/4 batches；live schema export `after_011_inventory_ledger_business_keys` 已生成 |
| Dry-run preview | 已开发；本地验证 prepared_rows=357 |
| Schema guard | 已开发；summary/detail flat-file schema guard 已接入 |
| Repository/upsert | 已开发，待 Azure SQL execute 验证 |
| Azure SQL execute | 待用户执行验证 |
| 幂等性验证 | 待用户重复 execute 验证 |
| 单元测试 | 已新增：mapping / dry-run / repo |
| 文档同步 | 本设计已完成第一版 |

功能整体状态：`Implemented`。`011` 已执行；Promotion/Coupon 已完成验收；Inventory Ledger 专用 dry-run / repository / CLI 已完成本地验证，已完成用户 dry-run、首次 execute 与第二次 execute 幂等性验证。

## 3. 业务目标

Inventory Ledger 的业务目标是解释库存变化，而不是替代库存快照：

1. 在周报中展示库存 movement：期初、入库、销售出库、退货、调拨、找到、丢失、损坏、报废、其他事件、期末。
2. 解释某个 SKU 为什么库存减少或增加。
3. 发现 FBA 丢件、损坏、adjustment、unknown events 等异常。
4. 辅助核对 FBA Reimbursements：丢失/损坏和赔偿是否匹配。
5. 为库存审计和异常提醒提供明细数据。

周报中的“当前剩余库存”优先使用：

```text
amazon_inventory_daily.afn_warehouse_quantity / afn_fulfillable_quantity / reserved 等字段
```

Inventory Ledger 用于补充：

```text
本周库存变化原因 = receipts + shipments + returns + transfers + adjustments 等 movement
```

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 `GET_LEDGER_SUMMARY_VIEW_DATA` flat file。
- 读取本地已下载的 `GET_LEDGER_DETAIL_VIEW_DATA` flat file。
- 校验 summary 当前观察到的 22 个源字段。
- 校验 detail 当前观察到的 16 个源字段。
- 解析每日库存 movement summary。
- 解析事件级库存流水 detail。
- 生成 `source_row_index`、`source_row_hash` 与 `business_key_hash`。
- 生成 DB-ready preview JSONL。
- 默认 dry-run，不写数据库。
- 显式 `--execute` 时写入 Azure SQL。
- 写入 `amazon_sync_run_log` 和 `amazon_schema_validation_event`。
- 支持重复 execute 幂等性验证。

### 4.2 本功能不包含

- 不替代 `amazon_inventory_daily` 当前库存快照。
- 不自动计算采购补货建议。
- 不自动生成库存预警或异常邮件。
- 不自动向 Amazon 创建 reimbursement claim。
- 不处理 Reserved Inventory / Inventory Planning / Restock Recommendations。
- 不做 Azure Container Apps Jobs 定时化。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports | `GET_LEDGER_SUMMARY_VIEW_DATA` | tab-delimited flat file | 已取样 150 行，22 个字段 | parser 已有，ingestion 待实现 | COUNTRY + DAILY 粒度库存 movement 汇总。 |
| SP-API Reports | `GET_LEDGER_DETAIL_VIEW_DATA` | tab-delimited flat file | 已取样 207 行，16 个字段 | parser 已有，ingestion 待实现 | 事件级库存 movement 明细。 |

当前样例：

| Report | raw file | row_count | field_count | sample doc |
|---|---|---:|---:|---|
| `GET_LEDGER_SUMMARY_VIEW_DATA` | `reports/raw/amazon/ATVPDKIKX0DER/GET_LEDGER_SUMMARY_VIEW_DATA/2026-05-14/112473020587.txt` | 150 | 22 | `requirements_to_be_deprecated/data_samples/GET_LEDGER_SUMMARY_VIEW_DATA.md` |
| `GET_LEDGER_DETAIL_VIEW_DATA` | `reports/raw/amazon/ATVPDKIKX0DER/GET_LEDGER_DETAIL_VIEW_DATA/2026-05-14/112479020587.txt` | 207 | 16 | `requirements_to_be_deprecated/data_samples/GET_LEDGER_DETAIL_VIEW_DATA.md` |

## 6. 源字段结构

### 6.1 Ledger Summary 字段

```text
Date
FNSKU
ASIN
MSKU
Title
Disposition
Starting Warehouse Balance
In Transit Between Warehouses
Receipts
Customer Shipments
Customer Returns
Vendor Returns
Warehouse Transfer In/Out
Found
Lost
Damaged
Disposed
Other Events
Ending Warehouse Balance
Unknown Events
Location
Store
```

### 6.2 Ledger Detail 字段

```text
Date
FNSKU
ASIN
MSKU
Title
Event Type
Reference ID
Quantity
Fulfillment Center
Disposition
Reason
Country
Reconciled Quantity
Unreconciled Quantity
Date and Time
Store
```

## 7. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/sp_api/{report_type}/{marketplace_id}/{timestamp}/...` | dry-run / execute 汇总。 |
| Schema events JSONL | 同上 | 入库前字段验证结果。 |
| Preview rows | `previews/*.preview.jsonl` | summary/detail DB-ready preview。 |
| Azure SQL tables | `dbo.amazon_inventory_ledger_summary_daily` / `dbo.amazon_inventory_ledger_detail` | 库存流水汇总与明细。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录 schema guard 结果。 |

## 8. 处理流程

建议实现为专用入口：

```text
local inventory ledger summary/detail raw files
  -> find latest raw files for both report types, or accept --summary-raw-file / --detail-raw-file
  -> decode flat files and detect delimiter
  -> validate expected fields
  -> parse rows with InventoryLedgerSummaryParser and InventoryLedgerDetailParser
  -> compute source_row_index per raw file
  -> compute source_row_hash from source raw row
  -> compute business_key_hash for each target row
  -> detect duplicate business keys within the same batch
  -> write DB-ready preview JSONL
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE summary/detail rows by business_key_hash
  -> insert schema validation event(s)
  -> update amazon_sync_run_log final status
  -> commit transaction
```

关键行为：

1. 默认 dry-run，不写数据库。
2. 只有显式 `--execute` 才允许写 Azure SQL。
3. Summary 或 detail 任一 report `requires_review=True` 时必须阻断 execute。
4. 写库必须通过 `get_connection()`，让 Azure SQL connection retry + `SELECT 1` warm-up 生效。
5. 同一 batch 内 business key 冲突但 payload 不一致时，必须 requires_review 并阻断 execute。

## 9. 字段映射

### 9.1 Ledger Summary

目标表：`dbo.amazon_inventory_ledger_summary_daily`

| 源字段 | 目标字段 | 说明 |
|---|---|---|
| `Date` | `ledger_date_raw` | 报告日期，保留原始字符串。 |
| `FNSKU` | `fnsku` | FNSKU。 |
| `ASIN` | `asin` | ASIN。 |
| `MSKU` | `seller_sku` | Seller SKU。 |
| `Title` | `title` | 商品标题。 |
| `Disposition` | `disposition` | SELLABLE / DEFECTIVE / CUSTOMER_DAMAGED 等。 |
| `Starting Warehouse Balance` | `starting_warehouse_balance` | 期初仓库余额。 |
| `In Transit Between Warehouses` | `in_transit_between_warehouses` | 仓间在途。 |
| `Receipts` | `receipts` | 入库。 |
| `Customer Shipments` | `customer_shipments` | 买家订单出库，通常为负数。 |
| `Customer Returns` | `customer_returns` | 买家退货。 |
| `Vendor Returns` | `vendor_returns` | 供应商退货。 |
| `Warehouse Transfer In/Out` | `warehouse_transfer_in_out` | 仓间调拨。 |
| `Found` | `found` | 找回库存。 |
| `Lost` | `lost` | 丢失库存。 |
| `Damaged` | `damaged` | 损坏库存。 |
| `Disposed` | `disposed` | 报废/处置。 |
| `Other Events` | `other_events` | 其他事件。 |
| `Ending Warehouse Balance` | `ending_warehouse_balance` | 期末仓库余额。 |
| `Unknown Events` | `unknown_events` | 未知事件。 |
| `Location` | `location` | 样例为 US。 |
| `Store` | `store` | 样例为空。 |

Business key 建议：

```text
source_report_type + marketplace_id + ledger_date_raw + seller_sku + fnsku + asin + disposition + location + store
```

### 9.2 Ledger Detail

目标表：`dbo.amazon_inventory_ledger_detail`

| 源字段 | 目标字段 | 说明 |
|---|---|---|
| `Date` | `ledger_date_raw` | 报告日期。 |
| `FNSKU` | `fnsku` | FNSKU。 |
| `ASIN` | `asin` | ASIN。 |
| `MSKU` | `seller_sku` | Seller SKU。 |
| `Title` | `title` | 商品标题。 |
| `Event Type` | `event_type` | Shipments、CustomerReturns、WhseTransfers、Adjustments、Receipts 等。 |
| `Reference ID` | `reference_id` | 事件参考号；很多行可能为空。 |
| `Quantity` | `quantity` | 事件数量。 |
| `Fulfillment Center` | `fulfillment_center` | FBA warehouse / FC。 |
| `Disposition` | `disposition` | SELLABLE / DEFECTIVE / CUSTOMER_DAMAGED 等。 |
| `Reason` | `reason` | adjustment reason；大部分为空。 |
| `Country` | `country` | 样例为 US。 |
| `Reconciled Quantity` | `reconciled_quantity` | 已核对数量。 |
| `Unreconciled Quantity` | `unreconciled_quantity` | 未核对数量。 |
| `Date and Time` | `date_time_raw` | 原始日期时间字符串。 |
| `Store` | `store` | 样例为空。 |

Business key 建议：

```text
source_report_type + marketplace_id + date_time_raw + seller_sku + fnsku + asin + event_type + reference_id + fulfillment_center + disposition + quantity + source_row_index
```

Detail report 中 `reference_id` 大量为空，同一天同 SKU 同 event_type 可能存在多个类似行。因此首版 detail business key 应包含 `source_row_index`，保证同一原始文件内重复样式行不会互相覆盖。若后续 Amazon 提供更稳定的事件 ID，再新增字段或调整 key 设计。

## 10. 数据库结构变更

当前两张目标表已存在，但缺少稳定 upsert 需要的 `business_key_hash` 和逻辑行号字段。已准备 migration：

```text
sql/migrations/011_add_inventory_ledger_business_keys.sql
```

该 migration 将为以下表增加：

```text
source_row_index INT NULL
business_key_hash NVARCHAR(100) NULL
```

并创建唯一过滤索引：

```text
UX_amazon_inventory_ledger_summary_daily_business_key_hash
UX_amazon_inventory_ledger_detail_business_key_hash
```

## 11. 周报使用口径

周报中建议这样使用库存数据：

| 周报问题 | 首选数据源 | 说明 |
|---|---|---|
| 当前还剩多少货 | `amazon_inventory_daily` | 使用最新库存快照，优先展示 fulfillable / warehouse / reserved / inbound 等字段。 |
| 本周为什么少了/多了 | `amazon_inventory_ledger_summary_daily` | 汇总 receipts、shipments、returns、lost、damaged、found 等 movement。 |
| 某个异常行怎么来的 | `amazon_inventory_ledger_detail` | 追踪 event_type、reference_id、FC、reason。 |
| 丢失/损坏是否赔偿 | `amazon_inventory_ledger_detail` + `amazon_fba_reimbursement` | 后续报表功能再做联动分析。 |

因此，Inventory Ledger 是周报库存模块的增强数据源，而不是 `amazon_inventory_daily` 的替代品。

## 12. 审计与可追溯性

每次 execute 必须写入：

- `amazon_sync_run_log`
- `amazon_schema_validation_event`
- 目标表的 `source_report_type`
- 目标表的 `source_report_id`
- 目标表的 `source_raw_file_path`
- 目标表的 `source_row_index`
- 目标表的 `source_row_hash`
- 目标表的 `raw_data`

当前项目仍允许 `source_raw_file_id` 暂时为 NULL；后续 raw file registry 完成后再补外键级追溯。

## 13. 验收标准

### 13.1 Migration 验收

```powershell
python scripts/run_sql_migration.py --file sql/migrations/011_add_inventory_ledger_business_keys.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/011_add_inventory_ledger_business_keys.sql
python scripts/export_database_schema_spec.py --output-prefix after_011_inventory_ledger_business_keys --include-row-counts
```

预期：

```text
011 dry-run: 4 executable batches
011 execute: 4/4 batches
live schema export 成功
```

### 13.2 Ingestion 验收

建议命令：

```powershell
python scripts/ingest_inventory_ledger_reports.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_inventory_ledger_reports.py --marketplace-id ATVPDKIKX0DER --execute
python scripts/ingest_inventory_ledger_reports.py --marketplace-id ATVPDKIKX0DER --execute
```

预期：

```text
dry-run: requires_review=False
首次 execute: inserted > 0, updated=0
第二次 execute: inserted=0, updated=首次 inserted 行数
```

基于当前样例，预期目标行数约为：

```text
amazon_inventory_ledger_summary_daily: 150
amazon_inventory_ledger_detail: 207
合计：357
```

## 14. 相关代码路径

已存在：

```text
src/seller_data_pipeline/parsers/amazon/inventory_ledger_parser.py
```

已新增：

```text
scripts/ingest_inventory_ledger_reports.py
src/seller_data_pipeline/ingestion/inventory_ledger_table_mapping.py
src/seller_data_pipeline/ingestion/inventory_ledger_ingestion_dry_run.py
src/seller_data_pipeline/ingestion/inventory_ledger_ingestion.py
src/seller_data_pipeline/db/repositories/inventory_ledger_repo.py
tests/unit/ingestion/test_inventory_ledger_table_mapping.py
tests/unit/ingestion/test_inventory_ledger_ingestion_dry_run.py
tests/unit/db/test_inventory_ledger_repo.py
```

## 15. 弃置记录

| 日期 | 方案 | 弃置原因 | 替代方案 |
|---|---|---|---|
| 2026-05-17 | 用 Inventory Ledger 替代库存快照 | Ledger 解释 movement，但当前库存余额应来自库存快照 report | 周报库存余额用 `amazon_inventory_daily`；movement 解释用 Ledger。 |
| 2026-05-17 | 只做 summary，不做 detail | Summary 适合周报，但无法追踪异常 reference/FC/reason | Summary/detail 两张表都做，周报先用 summary，异常排查用 detail。 |


## 16. 当前开发验证结果

本轮已实现专用入口：

```text
scripts/ingest_inventory_ledger_reports.py
```

本地 dry-run 验证结果：

```text
Inventory Ledger ingestion mode=dry_run status=dry_run_success
prepared_rows=357 requires_review=False
GET_LEDGER_SUMMARY_VIEW_DATA: parsed=150 prepared=150
  amazon_inventory_ledger_summary_daily: prepared=150
GET_LEDGER_DETAIL_VIEW_DATA: parsed=207 prepared=207
  amazon_inventory_ledger_detail: prepared=207
```

下一步验收命令：

```powershell
python scripts/ingest_inventory_ledger_reports.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_inventory_ledger_reports.py --marketplace-id ATVPDKIKX0DER --execute
python scripts/ingest_inventory_ledger_reports.py --marketplace-id ATVPDKIKX0DER --execute
```

预期首次 execute 插入 357 行；第二次 execute 更新 357 行且不重复插入。


## 13. Execute 验收结果

```text
Dry-run: prepared_rows=357 requires_review=False
首次 execute: sync_run_id=19, attempted=357 inserted=357 updated=0 written=357 skipped=0
第二次 execute: sync_run_id=20, attempted=357 inserted=0 updated=357 written=357 skipped=0
```
