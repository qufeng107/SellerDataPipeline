# Feature: Settlement Report Ingestion

> 文档状态：Implemented; v1.81 idempotency hardening implemented locally  
> 负责人：AI / 待定  
> 更新时间：2026-08-08  
> 功能状态：Implemented  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`

---

## 1. 功能摘要

本功能负责把 SP-API Reports 的 `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` 结算 flat file 转换为 Azure SQL 中的 normalized 财务明细表：

```text
GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2
  -> dbo.amazon_settlement_transaction
```

Settlement 是后续利润核算、费用归类、广告费用入账、Coupon/Deal 费用、FBA 费用、赔偿、退款、清算和回款核对的核心数据源。与 Sales & Traffic 不同，Settlement 更接近财务入账口径，但第一版只负责可靠入库和保守分类，不直接生成最终会计利润结论。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 数据源取样 | 已完成，8 份 raw file，4911 行 |
| 目标表 | 已存在于 `001_create_core_tables.sql` |
| 现有 parser | 已有 `src/seller_data_pipeline/parsers/amazon/settlement_report_parser.py` |
| 分类规则 | 已有第一版保守分类：`amount_category` / `profit_bucket` |
| 006 migration | 已执行成功：dry-run 4 batches，execute 4/4，live schema 已导出 |
| Dry-run preview | 已实现并验证：prepared_rows=4911，processed_files=8，requires_review=False |
| Schema guard | 已实现，基于 24 个 settlement required fields |
| Repository/upsert | 已实现并通过真实 execute 验证 |
| Azure SQL execute | 已验证：sync_run_id=9，inserted=4911 |
| 幂等性验证 | 已通过：sync_run_id=10，inserted=0 updated=4911 |
| 单元测试 | 已补齐 settlement mapping / dry-run / repository 测试 |

功能整体状态：`Implemented`。`006_add_settlement_transaction_business_key.sql` 已在 Azure SQL 执行成功，并已导出 `after_006_settlement_business_key.md/json` live schema。专用 ingestion 代码已完成并通过用户本地真实 Azure SQL 验收：dry-run `prepared_rows=4911`、`processed_files=8`、`requires_review=False`；首次 execute `sync_run_id=9`，`inserted=4911`；第二次 execute `sync_run_id=10`，`inserted=0 updated=4911`。

2026-08-05 monthly 自动化暴露 legacy idempotency compatibility bug：Settlement MERGE 同时按 `business_key_hash OR source identity` 匹配且 UPDATE 会改写 `business_key_hash`，在历史 legacy row 与 canonical row 并存时可能触发唯一索引冲突。v1.81 冻结修复为：**日常 MERGE 只按 canonical `business_key_hash`，business key immutable；legacy exact-source duplicates 由显式 dry-run/execute repair command 处理；失败 ingestion 必须 rollback normalized writes。** 详见 `feature_monthly_ingestion_recovery.md`。

## 3. 业务目标

本功能目标是沉淀可审计的 Amazon 结算明细，用于后续：

1. 按订单、SKU、结算周期拆解收入、退款、FBA fee、Referral fee、Coupon/Deal fee、广告扣费、仓储/入库费用、赔偿、清算等。
2. 作为利润核算的财务入账事实表，而不是仅依赖 Sales & Traffic 的销售口径。
3. 对接会计需要的月度/季度营业数据，减少手工整理 settlement report。
4. 为后续 `feature_profit_calculation.md` 提供 `amount_category` 和 `profit_bucket` 基础分类。

本功能不直接计算采购成本、头程、广告归因、SKU 毛利或最终会计利润；这些应由后续利润核算功能单独设计。

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` raw flat file。
- 支持多份 settlement raw file 批量 dry-run 和 execute。
- 校验 required fields：24 个 settlement 源字段。
- 识别 settlement summary 行，并把 summary 元数据向下继承到交易明细行。
- 保存 summary 行和 transaction 行，使用 `is_settlement_summary` 区分。
- 生成 `amount_category` 和 `profit_bucket` 第一版保守分类。
- 生成 DB-ready preview JSONL。
- 默认 dry-run，不写数据库。
- 显式 `--execute` 时写入 Azure SQL。
- 写入 `amazon_sync_run_log` 和 `amazon_schema_validation_event`。
- 支持重复 execute 幂等性验证。
- 保留完整 `raw_data` 和 `source_row_hash` 便于追溯。

### 4.2 本功能不包含

- 不主动 `createReport` 生成 settlement report；Settlement 当前通过 `getReports` discovery 下载 Amazon 自动生成的报告。
- 不做最终会计科目判断。
- 不把 `amount_category` / `profit_bucket` 视作不可变的会计结论。
- 不合并订单明细、库存、Ads campaign 维度或 SKU 成本。
- 不生成利润表、周报、月报或清仓建议。
- 不处理买家隐私数据；Settlement 样例当前不包含买家地址/contact 字段。
- 不做 Azure Container Apps Jobs 定时化。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | tab-delimited flat file | 已取样 8 份，4911 行 | parser / ingestion / upsert 已实现并验证 | Amazon 自动生成 settlement report，通常通过 discovery 下载。 |

当前聚合样例：

| 项目 | 当前值 |
|---|---|
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_count | `8` |
| row_count | `4911` |
| transaction_row_count | `4903` |
| settlement_summary_row_count | `8` |
| delimiter | tab |
| observed field count | `24` |
| sample doc | `requirements_to_be_deprecated/data_samples/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.md` |

当前 raw 路径约定：

```text
reports/raw/amazon/{marketplace_id}/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/{date}/{report_id}.txt
```

## 6. 源字段结构

当前 required fields：

```text
settlement-id
settlement-start-date
settlement-end-date
deposit-date
total-amount
currency
transaction-type
order-id
merchant-order-id
adjustment-id
shipment-id
marketplace-name
amount-type
amount-description
amount
fulfillment-id
posted-date
posted-date-time
order-item-code
merchant-order-item-id
merchant-adjustment-item-id
sku
quantity-purchased
promotion-id
```

重要语义：

1. 第一行通常是 settlement summary 行，包含 settlement id、settlement period、deposit date、total amount、currency。
2. 后续交易明细行通常不重复 summary 字段，需要 parser 继承当前 settlement summary。
3. `transaction-type`、`amount-type`、`amount-description` 是第一版费用分类的核心组合。
4. `sku` 对应目标字段 `seller_sku`。
5. `posted-date` 和 `posted-date-time` 当前先保留 raw string，后续如需标准化再新增 parsed datetime 字段或在分析层转换。

## 7. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/sp_api/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/{marketplace_id}/{timestamp}/...` | 本次 dry-run / execute 汇总。 |
| Schema events JSONL | 同上 | 入库前字段验证结果。 |
| Preview rows | `previews/amazon_settlement_transaction.preview.jsonl` | Settlement DB-ready preview。 |
| Azure SQL table | `dbo.amazon_settlement_transaction` | 结算明细和 summary 行。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录本 report 的 schema guard 结果。 |

## 8. 处理流程

按照已验证的 Listing / Inventory / Sales & Traffic 专用入口模式实现：

```text
local settlement raw files
  -> find latest raw files for marketplace/report_type, or accept --raw-file repeated explicit paths
  -> decode flat file and detect delimiter
  -> validate required settlement fields
  -> parse settlement summary rows and transaction rows
  -> inherit settlement summary metadata into detail rows
  -> classify amount_category / profit_bucket conservatively
  -> compute source_row_hash for each raw row
  -> compute source_row_index per raw file
  -> compute business_key_hash for each target row
  -> write DB-ready preview JSONL
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE rows into amazon_settlement_transaction by immutable business_key_hash only
  -> insert schema validation event(s)
  -> update amazon_sync_run_log final status
  -> commit transaction
```

关键行为：

1. 默认模式必须是 dry-run，不写数据库。
2. 只有显式传入 `--execute` 才允许写 Azure SQL。
3. 如果 schema guard 产生 `requires_review=True`，真实写库必须被阻断。
4. 写库必须通过 `get_connection()`，让 Azure SQL connection retry + `SELECT 1` warm-up 先完成。
5. 同一批多份 settlement raw file 应在同一 sync run 中处理；任一文件失败时整体 rollback，避免半批写入。
6. 不使用 `source_row_hash` 单独作为业务幂等键；必须使用 `business_key_hash`。
7. `business_key_hash` 是 canonical immutable key：MATCH/UPDATE 不允许通过 legacy natural-key fallback 改写该值。
8. 历史 exact source identity duplicates 必须通过 `scripts/repair_settlement_idempotency.py` 显式 dry-run/execute 修复，不在日常 ingestion 中静默删除。

## 9. 字段映射

| 源字段 | 目标字段 | 类型 | 说明 |
|---|---|---|---|
| CLI / report context | `marketplace_id` | string | Amazon marketplace id。 |
| `settlement-id` | `settlement_id` | string | summary 行直接读取；明细行继承当前 summary。 |
| `settlement-start-date` | `settlement_start_date_raw` | string | 原样保留。 |
| `settlement-end-date` | `settlement_end_date_raw` | string | 原样保留。 |
| `deposit-date` | `deposit_date_raw` | string | 原样保留。 |
| `total-amount` | `total_amount` | decimal | summary total amount；明细行继承时需谨慎，当前表已有字段。 |
| `currency` | `currency` | string | summary currency；明细行继承。 |
| summary row detection | `is_settlement_summary` | bit | summary 行为 1，明细行为 0。 |
| `transaction-type` | `transaction_type` | string | Order / Refund / ServiceFee / AmazonFees 等。 |
| `order-id` | `order_id` | string | Amazon order id。 |
| `merchant-order-id` | `merchant_order_id` | string | merchant order id。 |
| `adjustment-id` | `adjustment_id` | string | 调整 id。 |
| `shipment-id` | `shipment_id` | string | shipment id。 |
| `marketplace-name` | `marketplace_name` | string | 如 Amazon.com。 |
| `amount-type` | `amount_type` | string | ItemPrice / ItemFees / Promotion 等。 |
| `amount-description` | `amount_description` | string | Principal / Commission / FBAPerUnitFulfillmentFee 等。 |
| `amount` | `amount` | decimal | 单行金额。 |
| classification | `amount_category` | string | 第一版分类，如 product_sales / referral_fee / advertising_fee。 |
| classification | `profit_bucket` | string | 第一版利润桶，如 revenue / fba_fee / amazon_fee。 |
| `fulfillment-id` | `fulfillment_id` | string | 如 AFN。 |
| `posted-date` | `posted_date_raw` | string | 原样保留。 |
| `posted-date-time` | `posted_date_time_raw` | string | 原样保留。 |
| `order-item-code` | `order_item_code` | string | order item code。 |
| `merchant-order-item-id` | `merchant_order_item_id` | string | merchant order item id。 |
| `merchant-adjustment-item-id` | `merchant_adjustment_item_id` | string | merchant adjustment item id。 |
| `sku` | `seller_sku` | string | 卖家 SKU。 |
| `quantity-purchased` | `quantity_purchased` | int | 数量。 |
| `promotion-id` | `promotion_id` | string | promotion id。 |
| source metadata | `source_*`, `source_row_hash`, `raw_data` | mixed | 统一 ingestion 审计字段。 |
| computed | `source_row_index` | int | 建议 006 新增；每个 raw file 内的 1-based row index。 |
| computed | `business_key_hash` | string | 建议 006 新增；稳定业务幂等键。 |

## 10. 第一版分类规则

当前 parser 已有 `classify_settlement_amount()`，基于：

```text
transaction_type + amount_type + amount_description + is_settlement_summary
```

当前样例观察到的主要分类：

| amount_category | profit_bucket | 说明 |
|---|---|---|
| `product_sales` | `revenue` | 商品销售 principal。 |
| `shipping_revenue` | `revenue` | shipping 收入。 |
| `refund_revenue` | `refund` | 退款收入冲减。 |
| `referral_fee` | `amazon_fee` | Commission。 |
| `fba_fulfillment_fee` | `fba_fee` | FBAPerUnitFulfillmentFee。 |
| `promotion_discount` | `promotion_cost` | Promotion principal/shipping。 |
| `promotion_refund_adjustment` | `promotion_cost` | Refund 中 promotion 调整。 |
| `advertising_fee` | `advertising_cost` | Cost of Advertising。 |
| `coupon_fee` | `promotion_fee` | Coupon participation/performance fee。 |
| `deal_fee` | `promotion_fee` | Deal fee。 |
| `sales_tax` | `tax_passthrough` | Tax / ShippingTax。 |
| `marketplace_facilitator_tax` | `tax_passthrough` | MarketplaceFacilitatorTax。 |
| `inventory_reimbursement` | `reimbursement` | FBA Inventory Reimbursement。 |
| `storage_fee` | `fba_storage_fee` | Storage Fee。 |
| `liquidation_revenue` | `liquidation` | Liquidations principal。 |
| `liquidation_fee` | `liquidation_fee` | Liquidations brokerage fee。 |
| `settlement_summary` | `reconciliation` | summary row。 |
| `settlement_transfer` | `reconciliation` | Payable to Amazon / Successful charge 等。 |

分类规则必须保持保守：如果遇到新组合，不应静默归入错误类别，应标记为 `unknown` 或 `requires_review=True`，待人工确认。

## 11. 目标数据表设计

### 11.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.amazon_settlement_transaction` | yes | 结算 summary 和逐行交易明细 | planned MERGE/upsert |
| `dbo.amazon_sync_run_log` | yes | 任务审计 | insert then update |
| `dbo.amazon_schema_validation_event` | yes | schema guard 审计 | append-only insert |
| `dbo.amazon_raw_report_file` | yes | raw file registry | 后续应写入；本功能首版可先保存 path/hash |

### 11.2 业务主键 / 幂等键

Settlement raw file 可能被重复发现或重复下载，因此必须有稳定 upsert key。

当前 canonical key：

```text
business_key = marketplace_id + source_report_id + source_row_index + source_row_hash
business_key_hash = sha256(canonical JSON of business_key)
```

说明：

1. `source_report_id` 来自 Amazon report id / raw file stem，同一个 Amazon settlement report 重复下载时保持稳定。
2. **`source_raw_file_path` 不进入 canonical key**。同一 report 在不同 collect 日期下路径会变化，路径只能作为 provenance，不能制造新的财务业务行。
3. `source_row_index` 必须纳入 key，因为 settlement 中可能存在金额、描述、SKU 完全相同的重复行。
4. `source_row_hash` 用于确认同一 report row 的原始内容；同一个 report id + row index 如果内容变化，会生成新的 key，需要人工审视 Amazon 是否重发了不同内容。
5. v1.81 起 repository 只按 `business_key_hash` MERGE，UPDATE 不修改该 key；历史 legacy exact duplicates 通过显式 maintenance repair 处理。

### 11.3 新 migration 需求

`amazon_settlement_transaction` 已通过 006 增加 `business_key_hash` 和 `source_row_index`。

| 变化 | 原因 | migration 文件 | 状态 |
|---|---|---|---|
| 新增 `source_row_index INT NULL` | 支持同一文件内稳定定位和幂等 key | `006_add_settlement_transaction_business_key.sql` | executed, 4/4 batches |
| 新增 `business_key_hash NVARCHAR(100) NULL` | 支持稳定 MERGE/upsert 幂等键 | `006_add_settlement_transaction_business_key.sql` | executed, 4/4 batches |
| 新增 `UX_amazon_settlement_transaction_business_key_hash` | 防止重复插入同一 settlement raw row | `006_add_settlement_transaction_business_key.sql` | executed, 4/4 batches |

字段先允许 `NULL`，索引使用 filtered unique index：

```sql
WHERE business_key_hash IS NOT NULL
```

这样即使未来表中已有历史数据，也不会因为旧行缺少 business key 而导致 migration 失败；repository 写入时仍然必须要求新行生成非空 `business_key_hash`。

## 12. 幂等性设计

重复执行同一批 8 份 settlement raw file 应该安全。

当前样例预期行数：

```text
amazon_settlement_transaction: 4911 rows
```

预期验收：

```text
第一次 execute:
  attempted=4911 inserted=4911 updated=0

第二次 execute:
  attempted=4911 inserted=0 updated=4911

目标表总行数保持：4911
```

如果后续 repository 增加“完全相同内容不更新”的优化，也可以接受第二次 `updated=0 skipped=4911`，但绝对不应第二次再次插入相同行。

## 13. Schema guard 与异常处理

| 场景 | 处理方式 | 是否阻塞入库 | 是否记录 validation event |
|---|---|---|---|
| 缺少 required fields | 阻断 | yes | yes |
| delimiter 无法识别 | 阻断 | yes | yes if possible |
| decimal/int 解析失败 | 阻断 execute | yes | yes |
| 遇到未知 `transaction_type/amount_type/amount_description` 组合 | 第一版建议 requires_review=True，或记录 unknown 并阻断 execute | yes for first version | yes |
| settlement summary 行缺失 | 阻断或 requires_review | yes | yes |
| 明细行无法继承 settlement id/currency | 阻断或 requires_review | yes | yes |
| 空文件 | dry-run 显示 prepared_rows=0，execute 阻断或 no-op，需明确记录 | yes/no-op | yes |

## 14. 审计与可追溯性

| 审计对象 | 表/字段 | 说明 |
|---|---|---|
| 任务级审计 | `amazon_sync_run_log` | source_system=`sp_api_reports`，job_name 可用 `ingest_settlement_report`。 |
| schema guard | `amazon_schema_validation_event` | 每个 raw file 或本次批次记录 validation result。 |
| 原始文件路径 | `source_raw_file_path` | 当前先记录路径，后续补 raw file registry 外键。 |
| 原始报告 id | `source_report_id` | 可从文件名提取，例如 `100988020532`。 |
| 源行 hash | `source_row_hash` | 用于追溯源行内容。 |
| 源行序号 | `source_row_index` | 建议 006 新增，用于稳定定位。 |
| 原始行 | `raw_data` | 保存原始字段 JSON。 |


## 14.1 当前实现证据

截至本批更新，已完成：

```text
sql/migrations/006_add_settlement_transaction_business_key.sql
  dry-run: 4 executable batches
  execute: executed_batches=4/4

scripts/export_database_schema_spec.py --output-prefix after_006_settlement_business_key --include-row-counts
  json: runtime/schema_exports/after_006_settlement_business_key.json
  markdown: runtime/schema_exports/after_006_settlement_business_key.md

scripts/ingest_settlement_report.py --marketplace-id ATVPDKIKX0DER
  mode=dry_run
  prepared_rows=4911
  processed_files=8
  skipped_files=0
  requires_review=False

PYTHONPATH=src pytest -q
  152 passed
```

用户本地已完成真实 execute 和第二次 execute 幂等性验证：

```text
首次 execute: sync_run_id=9 inserted=4911 updated=0
第二次 execute: sync_run_id=10 inserted=0 updated=4911
```

结论：Settlement 入库链路已完成真实写库和幂等性验收。

## 15. CLI

已新增：

```powershell
python scripts/ingest_settlement_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_settlement_report.py --marketplace-id ATVPDKIKX0DER --execute
```

可选参数：

```text
--raw-file <path>      # 可重复传入；不传则默认找该 marketplace/report_type 下已下载 raw files
--output-dir <path>
--max-files <n>        # 开发调试时限制文件数；execute 时默认不建议使用
```

说明：按照 `ADR-005-progressive-generalization.md`，当前仍采用专用入口，不急于做通用 `ingest_sp_api_reports.py`。

## 16. 相关代码路径

已有：

| 路径 | 用途 |
|---|---|
| `src/seller_data_pipeline/parsers/amazon/settlement_report_parser.py` | 已有 settlement parser、required fields、summary 继承、分类规则。 |
| `scripts/analyze_settlement_reports.py` | 已有 settlement 样例分析脚本。 |
| `requirements_to_be_deprecated/data_samples/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.md` | 当前 settlement 聚合取样记录。 |

已新增：

| 路径 | 用途 |
|---|---|
| `scripts/ingest_settlement_report.py` | Settlement 专用 CLI。 |
| `src/seller_data_pipeline/ingestion/settlement_table_mapping.py` | 字段映射、expected schema、DB row 生成。 |
| `src/seller_data_pipeline/ingestion/settlement_ingestion_dry_run.py` | dry-run preview 与 schema guard。 |
| `src/seller_data_pipeline/ingestion/settlement_ingestion.py` | execute orchestration。 |
| `src/seller_data_pipeline/db/repositories/settlement_repo.py` | Azure SQL MERGE/upsert repository。 |
| `tests/unit/ingestion/test_settlement_table_mapping.py` | 字段映射测试。 |
| `tests/unit/ingestion/test_settlement_ingestion_dry_run.py` | dry-run 测试。 |
| `tests/unit/db/test_settlement_repo.py` | repository SQL/upsert 行为测试。 |

## 17. 验收标准

### 17.1 设计与数据库验收

- 本文档完成并进入 `docs/features/README.md` 索引。
- `006_add_settlement_transaction_business_key.sql` 已创建。
- 006 dry-run 应显示 `4 executable batches`。
- 006 在 Azure SQL 执行成功。
- 已运行 `scripts/export_database_schema_spec.py --output-prefix after_006_settlement_business_key --include-row-counts`。
- `docs/database/database_current_schema_spec.md` 已据真实 schema 更新 `source_row_index`、`business_key_hash` 和唯一过滤索引。

### 17.2 代码验收

- `python scripts/ingest_settlement_report.py --marketplace-id ATVPDKIKX0DER` dry-run 成功。
- dry-run 输出合计 `prepared_rows=4911`、`requires_review=False` 或明确说明需要 review 的未知分类。
- `--execute` 首次写入成功。
- 第二次 `--execute` 幂等性通过。
- `amazon_settlement_transaction` 行数与 expected rows 一致。
- `amazon_sync_run_log` 有成功记录。
- `amazon_schema_validation_event` 有 `validation_status=ok` 或可解释 warning 记录。
- `pytest` 通过。
- `compileall` 通过。
- 本功能文档、progress 文档、数据库 spec 同步完成。

## 18. 当前限制与后续优化

1. 当前分类规则是第一版运营分类，不等同会计最终科目。
2. 当前 `posted_date_raw` / `posted_date_time_raw` / settlement date 字段先保留 raw string，后续可在分析层或新字段中标准化。
3. `total_amount` 在明细行中是否继承 summary 值需要谨慎；如只用于 summary 行，可在 mapping 中明确。
4. Settlement 中 `Cost of Advertising` 可提供财务入账广告费，但 campaign/keyword 维度仍来自 Ads API。
5. 当前不写 `amazon_raw_report_file` 外键；后续应补 raw registry。
6. 4911 行样例来自当前账号当前窗口，后续新 transaction/amount 组合应触发 schema/classification review。

## 19. 弃置记录

| 日期 | 方案 | 处理 | 原因 |
|---|---|---|---|
| 2026-05-17 | 在 Settlement ingestion 中直接计算最终利润 | 暂缓 | Settlement 是利润核算输入之一，最终利润还需要 Ads、SKU cost、Orders、FBA fees、Reimbursements 等数据共同计算。 |
| 2026-05-17 | 直接做通用 `ingest_sp_api_reports.py` 支持所有 SP-API reports | 暂缓 | 按渐进式抽象规则，Settlement 仍先采用专用入口，确保财务数据链路可审计。 |
