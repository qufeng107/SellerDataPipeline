# Feature: FBA Reimbursements Report Ingestion

> 文档状态：Implemented; 008 executed; execute and idempotency validated  
> 负责人：AI / 待定  
> 更新时间：2026-05-17  
> 功能状态：Implemented  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`

---

## 1. 功能摘要

本功能负责把 SP-API Reports 的 `GET_FBA_REIMBURSEMENTS_DATA` FBA 赔偿 flat file 转换为 Azure SQL 中的 normalized 赔偿事实表：

```text
GET_FBA_REIMBURSEMENTS_DATA
  -> dbo.amazon_fba_reimbursement
```

FBA Reimbursements 是利润核算的重要补充数据源。Settlement 记录实际入账和扣费流水，但 FBA Reimbursements report 能更直接地说明 Amazon 因客户退货、仓库损坏、仓库丢失、客服问题、reversal 等原因赔偿现金或库存的明细。第一版只做可靠入库和保守字段映射，不直接把赔偿金额并入最终利润模型。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 数据源取样 | 已完成，1 份 raw file，19 行，18 个源字段 |
| 目标表 | 已存在于 `001_create_core_tables.sql`：`dbo.amazon_fba_reimbursement` |
| Parser | 已存在：`src/seller_data_pipeline/parsers/amazon/fba_reimbursements_parser.py` |
| Migration | 已执行：`008_add_fba_reimbursement_business_key.sql`，4/4 batches；live schema 已导出 |
| Dry-run preview | 已开发并验证：`prepared_rows=19 requires_review=False` |
| Schema guard | 已开发，expected fields=18，当前样例匹配通过 |
| Repository/upsert | 已开发：`FbaReimbursementsRepo` / MERGE by `business_key_hash` |
| Azure SQL execute | 已完成：`sync_run_id=13`，inserted=19 updated=0 |
| 幂等性验证 | 已完成：`sync_run_id=14`，inserted=0 updated=19 |
| 单元测试 | 已新增并通过 |
| 文档同步 | 本设计已完成第一版 |

功能整体状态：`Implemented`。`008_add_fba_reimbursement_business_key.sql` 已由用户本地 dry-run、执行成功，并运行 live schema export；FBA Reimbursements 专用 dry-run、schema guard、repository、CLI、首次 execute 和第二次 execute 幂等性验证均已完成。

## 3. 业务目标

本功能已沉淀 Amazon FBA 赔偿事实，用于后续：

1. 按 SKU / ASIN 查看现金赔偿、库存赔偿、赔偿 reversal 和赔偿原因。
2. 区分正向赔偿与负向 reversal，避免利润核算遗漏 Amazon 赔偿或重复计算。
3. 与 Settlement 中的 reimbursement 相关 transaction 对账。
4. 与 Inventory Ledger、Orders、Returns 等数据联动，分析丢失、损坏、客户退货带来的成本和赔偿。
5. 为周报/月报提供“赔偿收入 / 赔偿 reversal / 赔库存数量”辅助指标。

FBA Reimbursements 数据不是最终利润唯一口径。最终利润仍需结合 Settlement、Orders、Ads、SKU cost、FBA fees、Coupon/Promotion 等数据统一计算。

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 `GET_FBA_REIMBURSEMENTS_DATA` raw flat file。
- 校验当前观察到的 18 个源字段。
- 解析 approval date、reimbursement id、case id、order id、reason、SKU/FNSKU/ASIN、金额、现金赔偿数量、库存赔偿数量、original reimbursement 信息。
- 生成 `source_row_index`、`source_row_hash` 和 `business_key_hash`。
- 生成 DB-ready preview JSONL。
- 默认 dry-run，不写数据库。
- 显式 `--execute` 时写入 Azure SQL。
- 写入 `amazon_sync_run_log` 和 `amazon_schema_validation_event`。
- 支持重复 execute 幂等性验证。

### 4.2 本功能不包含

- 不做最终利润计算。
- 不把 FBA Reimbursements 与 Settlement 自动强匹配；对账功能后续单独设计。
- 不处理 FBA fee preview、customer returns、inventory ledger 等其他 report。
- 不根据赔偿原因自动调整库存或成本。
- 不做 Azure Container Apps Jobs 定时化。
- 不重构现有表为多表模型；第一版复用 `amazon_fba_reimbursement`。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports | `GET_FBA_REIMBURSEMENTS_DATA` | tab-delimited flat file | 已取样 1 份，19 行 | parser / ingestion / upsert 已实现并验证 | FBA 赔偿明细。 |

当前样例：

| 项目 | 当前值 |
|---|---|
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FBA_REIMBURSEMENTS_DATA/2026-05-14/112469020587.txt` |
| row_count | `19` |
| field_path_count | `18` |
| delimiter | tab |
| encoding | cp1252 |
| sample doc | `requirements_to_be_deprecated/data_samples/GET_FBA_REIMBURSEMENTS_DATA.md` |

## 6. 源字段结构

当前观察到的 18 个源字段：

```text
approval-date
reimbursement-id
case-id
amazon-order-id
reason
sku
fnsku
asin
product-name
condition
currency-unit
amount-per-unit
amount-total
quantity-reimbursed-cash
quantity-reimbursed-inventory
quantity-reimbursed-total
original-reimbursement-id
original-reimbursement-type
```

当前样例中 `reason` 包括：

```text
CustomerReturn
Damaged_Warehouse
Reimbursement_Reversal
CustomerServiceIssue
```

注意：`amount-total` 和 `amount-per-unit` 可能为负数。负数通常代表 reversal 或扣回，不应在后续利润模型中简单按绝对值处理。

## 7. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/sp_api/GET_FBA_REIMBURSEMENTS_DATA/{marketplace_id}/{timestamp}/...` | 本次 dry-run / execute 汇总。 |
| Schema events JSONL | 同上 | 入库前字段验证结果。 |
| Preview rows | `previews/amazon_fba_reimbursement.preview.jsonl` | FBA Reimbursement DB-ready preview。 |
| Azure SQL table | `dbo.amazon_fba_reimbursement` | FBA 赔偿事实表。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录本 report 的 schema guard 结果。 |

## 8. 处理流程

按已验证的专用入口模式实现：

```text
local FBA reimbursements raw file
  -> find latest raw file for marketplace/report_type, or accept --raw-file explicit path
  -> decode flat file and detect delimiter
  -> validate expected fields
  -> parse rows with FbaReimbursementsParser
  -> compute source_row_index per raw file
  -> compute source_row_hash for each raw row
  -> compute business_key_hash for each target row
  -> detect duplicate business keys within the same batch
  -> write DB-ready preview JSONL
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE rows into amazon_fba_reimbursement by business_key_hash
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
| `approval-date` | `approval_date_raw` | string | yes | Amazon 批准赔偿时间，原样保存。 |
| `reimbursement-id` | `reimbursement_id` | string | yes | Amazon reimbursement id。 |
| `case-id` | `case_id` | string | no | Amazon case id；当前样例为空。 |
| `amazon-order-id` | `amazon_order_id` | string | no | 关联订单 id；部分赔偿行可能为空。 |
| `reason` | `reason` | string | yes | 赔偿原因或 reversal 类型。 |
| `sku` | `seller_sku` | string | yes | 卖家 SKU。 |
| `fnsku` | `fnsku` | string | yes | FBA FNSKU。 |
| `asin` | `asin` | string | yes | ASIN。 |
| `product-name` | `product_name` | string | no | 商品名。 |
| `condition` | `condition` | string | no | 商品状态，样例为 `NewItem`。 |
| `currency-unit` | `currency` | string | yes | 币种，样例为 USD。 |
| `amount-per-unit` | `amount_per_unit` | decimal | yes | 单位赔偿金额，可为负数。 |
| `amount-total` | `amount_total` | decimal | yes | 总赔偿金额，可为负数。 |
| `quantity-reimbursed-cash` | `quantity_reimbursed_cash` | int | yes | 现金赔偿对应数量，可为负数。 |
| `quantity-reimbursed-inventory` | `quantity_reimbursed_inventory` | int | yes | 库存赔偿对应数量，可为负数。 |
| `quantity-reimbursed-total` | `quantity_reimbursed_total` | int | yes | 总赔偿数量。 |
| `original-reimbursement-id` | `original_reimbursement_id` | string | no | reversal 对应的原赔偿 id。 |
| `original-reimbursement-type` | `original_reimbursement_type` | string | no | reversal 对应原赔偿类型。 |

### 9.2 标准字段到数据库字段

目标表 `dbo.amazon_fba_reimbursement` 已包含以上主要字段。`008_add_fba_reimbursement_business_key.sql` 已执行并新增：

| 标准字段 | 目标表 | 目标字段 | 类型 | 转换规则 |
|---|---|---|---|---|
| computed row index | `dbo.amazon_fba_reimbursement` | `source_row_index` | INT | raw file 内 1-based data row index。 |
| computed business key | `dbo.amazon_fba_reimbursement` | `business_key_hash` | NVARCHAR(100) | 对 canonical business key 做 sha256。 |

## 10. 目标数据表设计

### 10.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.amazon_fba_reimbursement` | yes | FBA 赔偿明细事实表。 | MERGE/upsert |
| `dbo.amazon_sync_run_log` | yes | 任务级审计。 | insert/update |
| `dbo.amazon_schema_validation_event` | yes | schema guard 记录。 | insert |

### 10.2 业务主键 / 幂等键

首版建议：

```text
business_key = marketplace_id
             + source_report_type
             + reimbursement_id
             + seller_sku
             + fnsku
             + asin
             + approval_date_raw
             + amount_total
             + quantity_reimbursed_total
```

理由：

1. `reimbursement-id` 是赔偿事件的核心标识。
2. SKU/FNSKU/ASIN 帮助限定同一 reimbursement 内的商品行。
3. `approval-date`、金额和数量提供额外防冲突能力。
4. `reason` 不进入 key，避免 Amazon 未来修正 reason 时导致重复插入。

风险：如果同一 reimbursement id 下同一 SKU/FNSKU/ASIN 有多条金额/数量完全相同的行，仍可能冲突。第一版 dry-run 必须检测重复 business key；如重复 key 对应不同 raw row，阻断 execute 并人工判断是否把 `source_row_index` 纳入 key。

### 10.3 Migration 状态

| 变更 | 原因 | Migration | 当前状态 |
|---|---|---|---|
| 新增 `source_row_index INT NULL` | 源文件行级追溯和冲突排查。 | `008_add_fba_reimbursement_business_key.sql` | executed, 4/4 batches |
| 新增 `business_key_hash NVARCHAR(100) NULL` | 支持稳定 MERGE/upsert 幂等。 | `008_add_fba_reimbursement_business_key.sql` | executed, 4/4 batches |
| 新增唯一过滤索引 `UX_amazon_fba_reimbursement_business_key_hash` | 防止重复插入同一 reimbursement 行。 | `008_add_fba_reimbursement_business_key.sql` | executed, 4/4 batches |

`008` 已在 Azure SQL 执行成功，并已导出 `after_008_fba_reimbursement_business_key` live schema；`docs/database/database_current_schema_spec.md` 已记录新增字段和唯一过滤索引。

## 11. Schema guard 规则

### 11.1 Expected fields

首版 expected fields 固定为当前观察到的 18 个字段。缺失 required fields 时：

```text
validation_status = missing_required_fields
severity = error
requires_review = True
```

新增字段时：

```text
validation_status = unexpected_fields
severity = warning
requires_review = True
```

字段完全匹配时：

```text
validation_status = ok
severity = info
requires_review = False
```

### 11.2 数据级 guard

以下情况应阻断 execute：

1. `reimbursement_id` 为空。
2. `seller_sku`、`fnsku`、`asin` 同时缺失。
3. `currency` 为空但金额非空。
4. `amount_total` 无法解析为 decimal。
5. 同一批次出现重复 business key 且 raw row 不完全一致。

## 12. 审计与可追溯性

每次 execute 必须写入：

```text
amazon_sync_run_log
amazon_schema_validation_event
```

目标表每行必须保留：

```text
source_report_type
source_report_id
source_raw_file_path
source_run_id
source_row_index
source_row_hash
business_key_hash
raw_data
```

当前 raw file 外键链路仍有改进空间：`source_raw_file_id` 可能继续为 NULL。后续应统一 raw report file registry，再补强外键追溯。

## 13. 建议 CLI

建议新增专用入口：

```powershell
python scripts/ingest_fba_reimbursements_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_fba_reimbursements_report.py --marketplace-id ATVPDKIKX0DER --execute
```

可选参数：

```text
--raw-file explicit/path/to/report.txt
--report-id optional_report_id
--snapshot-date optional business date if needed later
```

## 14. 相关代码路径

已新增：

```text
scripts/ingest_fba_reimbursements_report.py
src/seller_data_pipeline/ingestion/fba_reimbursements_table_mapping.py
src/seller_data_pipeline/ingestion/fba_reimbursements_ingestion_dry_run.py
src/seller_data_pipeline/ingestion/fba_reimbursements_ingestion.py
src/seller_data_pipeline/db/repositories/fba_reimbursements_repo.py
```

已存在 parser：

```text
src/seller_data_pipeline/parsers/amazon/fba_reimbursements_parser.py
```

已新增测试：

```text
tests/unit/ingestion/test_fba_reimbursements_table_mapping.py
tests/unit/ingestion/test_fba_reimbursements_ingestion_dry_run.py
tests/unit/db/test_fba_reimbursements_repo.py
```

## 15. 验收标准

第一版功能完成必须满足：

1. `008_add_fba_reimbursement_business_key.sql` dry-run batch 数正常。
2. `008` 在 Azure SQL 执行成功。
3. `export_database_schema_spec.py --output-prefix after_008_fba_reimbursement_business_key --include-row-counts` 导出成功。
4. `database_current_schema_spec.md` 记录真实新增字段和索引。
5. dry-run 成功：`prepared_rows=19 requires_review=False`。
6. 首次 `--execute` 成功：`sync_run_id=13`，attempted=19 inserted=19 updated=0 written=19 skipped=0。
7. 第二次 `--execute` 成功：`sync_run_id=14`，attempted=19 inserted=0 updated=19 written=19 skipped=0。
8. `amazon_sync_run_log` 有成功记录。
9. `amazon_schema_validation_event` 无 blocking error。
10. 单元测试通过。
11. `compileall` 通过。
12. 文档同步：本 feature 文档、features README、progress、current schema spec。

## 16. 当前限制与后续优化

1. `source_raw_file_id` 可能仍为 NULL，后续应统一 raw file registry。
2. Reimbursements 与 Settlement 的对账逻辑尚未设计。
3. Reimbursement reason 分类是否需要标准化枚举，留到利润核算阶段确认。
4. Reversal 和负数金额在后续利润模型中必须保留符号，不可取绝对值。
5. 当前 business key 是保守首版；如 dry-run 发现冲突，应先调整设计文档再写代码。

## 17. 变更记录

| 日期 | 事项 | 证据 | 备注 |
|---|---|---|---|
| 2026-05-17 | 完成 FBA Reimbursements 入库功能设计第一版 | 本文档 | 下一步准备 008 migration。 |
| 2026-05-17 | 准备 `008_add_fba_reimbursement_business_key.sql` | `python scripts/run_sql_migration.py --file sql/migrations/008_add_fba_reimbursement_business_key.sql --dry-run --show-batches` -> `4 executable batches` | 已由用户本地执行。 |
| 2026-05-17 | 执行 `008` 并导出 live schema | 用户本地执行：`executed_batches=4/4`；`after_008_fba_reimbursement_business_key.md/json` | current schema spec 已同步。 |
| 2026-05-17 | 开发 FBA Reimbursements 专用 ingestion 并完成 dry-run | `python scripts/ingest_fba_reimbursements_report.py --marketplace-id ATVPDKIKX0DER` -> `prepared_rows=19 requires_review=False`；`pytest=167 passed` | 已进入 execute 验收。 |
| 2026-05-17 | 完成 FBA Reimbursements 真实 execute 与幂等性验证 | 首次 execute：`sync_run_id=13 attempted=19 inserted=19 updated=0`；第二次 execute：`sync_run_id=14 attempted=19 inserted=0 updated=19` | 功能状态更新为 `Implemented`。 |

## 18. 弃置记录

暂无。
