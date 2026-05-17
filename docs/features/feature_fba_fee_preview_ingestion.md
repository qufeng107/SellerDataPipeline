# Feature: FBA Fee Preview Report Ingestion

> 文档状态：Implemented; 009 executed; dry-run, Azure SQL execute and idempotency verified  
> 负责人：AI / 待定  
> 更新时间：2026-05-17  
> 功能状态：Implemented  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`

---

## 1. 功能摘要

本功能负责把 SP-API Reports 的 `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` FBA 费用预估 flat file 转换为 Azure SQL 中的 SKU/ASIN 维度费用预估表：

```text
GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA
  -> dbo.amazon_fba_fee_preview
```

FBA Fee Preview 用于后续利润核算中的参考费用口径，尤其是 SKU/ASIN 的预估 referral fee、expected fulfillment fee、尺寸重量、size tier、币种、价格等字段。它不是实际扣费流水，最终利润仍以 Settlement 为主口径；本表主要用于商品维度的预估利润、异常费用对比和 listing/SKU 资料补充。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 数据源取样 | 已完成，1 份 raw file，8 行，31 个源字段 |
| 目标表 | 已存在于 `001_create_core_tables.sql`：`dbo.amazon_fba_fee_preview` |
| Parser | 已存在：`src/seller_data_pipeline/parsers/amazon/fba_estimated_fees_parser.py` |
| Migration | 已执行：`009_add_fba_fee_preview_business_key.sql`，4/4 batches；live schema 已导出 `after_009_fba_fee_preview_business_key` |
| Dry-run preview | 已开发并验证：prepared_rows=8 requires_review=False |
| Schema guard | 已开发，expected fields=31，当前样例 status=ok |
| Repository/upsert | 已开发，待 Azure SQL execute 验证 |
| Azure SQL execute | 已完成；首次 execute sync_run_id=15，inserted=8 updated=0 |
| 幂等性验证 | 已完成；第二次 execute sync_run_id=16，inserted=0 updated=8 |
| 单元测试 | 已新增并通过 |
| 文档同步 | 本设计已完成第一版 |

功能整体状态：`Implemented`。`009_add_fba_fee_preview_business_key.sql` 已在 Azure SQL 执行成功并导出 live schema；专用 ingestion 链路已完成 dry-run、首次 execute 和第二次 execute 幂等性验证。

## 3. 业务目标

本功能目标是沉淀 Amazon 提供的 FBA 费用预估数据，用于后续：

1. 按 SKU / ASIN 查看预估 referral fee 和 FBA fulfillment fee。
2. 为新品和现有 SKU 的预估利润模型提供费用参考。
3. 与 Settlement 中实际扣费对比，识别费用异常或 size tier 变化带来的成本变化。
4. 沉淀商品尺寸、重量、size tier、fulfilled_by、product_group 等运营字段。
5. 为周报/月报提供“预估 FBA fee / 预估 referral fee / size tier”辅助指标。

本 report 是预估口径，不应替代 Settlement 中的实际扣费；利润核算应把本表作为补充或预测输入。

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` raw flat file。
- 校验当前观察到的 31 个源字段。
- 解析 SKU/FNSKU/ASIN、store、商品维度、价格、尺寸重量、size tier、币种和各类预估费用。
- 生成 `source_row_index`、`source_row_hash` 和 `business_key_hash`。
- 生成 DB-ready preview JSONL。
- 默认 dry-run，不写数据库。
- 显式 `--execute` 时写入 Azure SQL。
- 写入 `amazon_sync_run_log` 和 `amazon_schema_validation_event`。
- 支持重复 execute 幂等性验证。

### 4.2 本功能不包含

- 不计算最终利润。
- 不把预估费用自动覆盖 Settlement 实际费用。
- 不自动调整商品成本、售价或广告策略。
- 不处理 FBA Reimbursements、Orders、Settlement 等其他 report。
- 不做 Azure Container Apps Jobs 定时化。
- 不引入多版本费用模型；第一版只按 report 当前行级内容保守入库。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | tab-delimited flat file | 已取样 1 份，8 行 | parser 已有，ingestion 待实现 | SKU/ASIN 费用预估。 |

当前样例：

| 项目 | 当前值 |
|---|---|
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA/2026-05-14/112470020587.txt` |
| row_count | `8` |
| field_path_count | `31` |
| delimiter | tab |
| encoding | cp1252 |
| sample doc | `requirements_to_be_deprecated/data_samples/GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA.md` |

## 6. 源字段结构

当前观察到的 31 个源字段：

```text
sku
fnsku
asin
amazon-store
product-name
product-group
brand
fulfilled-by
your-price
sales-price
longest-side
median-side
shortest-side
length-and-girth
unit-of-dimension
item-package-weight
unit-of-weight
product-size-tier
currency
estimated-fee-total
estimated-referral-fee-per-unit
estimated-variable-closing-fee
estimated-order-handling-fee-per-order
estimated-pick-pack-fee-per-unit
estimated-weight-handling-fee-per-unit
expected-fulfillment-fee-per-unit
estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)
estimated-future-order-handling-fee-per-order
estimated-future-pick-pack-fee-per-unit
estimated-future-weight-handling-fee-per-unit
expected-future-fulfillment-fee-per-unit
```

当前样例包含 `amazon-store`，观察值包括 `US` 与 `CA`。因为同一个 marketplace 报告样例中可能出现多个 store，首版 business key 必须包含 `amazon_store`，避免 US/CA 行互相覆盖。

## 7. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/sp_api/GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA/{marketplace_id}/{timestamp}/...` | 本次 dry-run / execute 汇总。 |
| Schema events JSONL | 同上 | 入库前字段验证结果。 |
| Preview rows | `previews/amazon_fba_fee_preview.preview.jsonl` | FBA Fee Preview DB-ready preview。 |
| Azure SQL table | `dbo.amazon_fba_fee_preview` | SKU/ASIN 费用预估事实表。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录本 report 的 schema guard 结果。 |

## 8. 处理流程

按已验证的专用入口模式实现：

```text
local FBA fee preview raw file
  -> find latest raw file for marketplace/report_type, or accept --raw-file explicit path
  -> decode flat file and detect delimiter
  -> validate expected fields
  -> parse rows with FbaEstimatedFeesParser
  -> compute source_row_index per raw file
  -> compute source_row_hash for each raw row
  -> compute business_key_hash for each target row
  -> detect duplicate business keys within the same batch
  -> write DB-ready preview JSONL
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE rows into amazon_fba_fee_preview by business_key_hash
  -> insert schema validation event(s)
  -> update amazon_sync_run_log final status
  -> commit transaction
```

关键行为：

1. 默认 dry-run，不写数据库。
2. 只有显式 `--execute` 才允许写 Azure SQL。
3. `requires_review=True` 时必须阻断 execute。
4. 写库必须通过 `get_connection()`，让 Azure SQL connection retry + `SELECT 1` warm-up 生效。
5. 同一 raw file 内如果出现重复 business key 且源行内容不同，必须 requires_review 并阻断 execute。

## 9. 字段映射

### 9.1 源字段到标准字段

| 源字段 | 标准字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|---|
| `sku` | `seller_sku` | string | yes | 卖家 SKU。 |
| `fnsku` | `fnsku` | string | yes | FBA FNSKU。 |
| `asin` | `asin` | string | yes | ASIN。 |
| `amazon-store` | `amazon_store` | string | yes | 报告中的 store，样例含 US/CA。 |
| `product-name` | `product_name` | string | no | 商品名。 |
| `product-group` | `product_group` | string | no | 商品组，样例为 Luggage。 |
| `brand` | `brand` | string | no | 品牌。 |
| `fulfilled-by` | `fulfilled_by` | string | yes | 样例为 Amazon。 |
| `your-price` | `your_price` | decimal | yes | 当前价格。 |
| `sales-price` | `sales_price` | decimal | yes | 销售价格。 |
| `longest-side` | `longest_side` | decimal | no | 最长边。 |
| `median-side` | `median_side` | decimal | no | 中间边。 |
| `shortest-side` | `shortest_side` | decimal | no | 最短边。 |
| `length-and-girth` | `length_and_girth` | decimal | no | 长度和周长。 |
| `unit-of-dimension` | `unit_of_dimension` | string | no | 尺寸单位，样例含 centimeters/inches。 |
| `item-package-weight` | `item_package_weight` | decimal | no | 包裹重量。 |
| `unit-of-weight` | `unit_of_weight` | string | no | 重量单位，样例含 grams/pounds。 |
| `product-size-tier` | `product_size_tier` | string | no | FBA size tier。 |
| `currency` | `currency` | string | yes | 币种，样例含 CAD/USD。 |
| `estimated-fee-total` | `estimated_fee_total` | decimal | yes | 当前 selling on Amazon + fulfillment fees 预估总费用。 |
| `estimated-referral-fee-per-unit` | `estimated_referral_fee_per_unit` | decimal | yes | 预估 referral fee。 |
| `estimated-variable-closing-fee` | `estimated_variable_closing_fee` | decimal | no | 预估 variable closing fee。 |
| `estimated-order-handling-fee-per-order` | `estimated_order_handling_fee_per_order` | decimal | no | 可能为 `--`，解析为 NULL。 |
| `estimated-pick-pack-fee-per-unit` | `estimated_pick_pack_fee_per_unit` | decimal | no | 可能为 `--`，解析为 NULL。 |
| `estimated-weight-handling-fee-per-unit` | `estimated_weight_handling_fee_per_unit` | decimal | no | 可能为 `--`，解析为 NULL。 |
| `expected-fulfillment-fee-per-unit` | `expected_fulfillment_fee_per_unit` | decimal | yes | 预估 fulfillment fee。 |
| `estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)` | `estimated_future_fee_total` | decimal | no | 可能为 `--`，解析为 NULL。 |
| `estimated-future-order-handling-fee-per-order` | `estimated_future_order_handling_fee_per_order` | decimal | no | 可能为 `--`。 |
| `estimated-future-pick-pack-fee-per-unit` | `estimated_future_pick_pack_fee_per_unit` | decimal | no | 可能为 `--`。 |
| `estimated-future-weight-handling-fee-per-unit` | `estimated_future_weight_handling_fee_per_unit` | decimal | no | 可能为 `--`。 |
| `expected-future-fulfillment-fee-per-unit` | `expected_future_fulfillment_fee_per_unit` | decimal | no | 可能为 `--`。 |

### 9.2 标准字段到数据库字段

目标表 `dbo.amazon_fba_fee_preview` 已包含主要 report 字段。首版仍需新增：

| 标准字段 | 目标表 | 目标字段 | 类型 | 转换规则 |
|---|---|---|---|---|
| computed row index | `dbo.amazon_fba_fee_preview` | `source_row_index` | INT | raw file 内 1-based data row index。 |
| computed business key | `dbo.amazon_fba_fee_preview` | `business_key_hash` | NVARCHAR(100) | 对 canonical business key 做 sha256。 |

## 10. 目标数据表设计

### 10.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.amazon_fba_fee_preview` | yes | SKU/ASIN 维度费用预估事实表。 | MERGE/upsert |
| `dbo.amazon_sync_run_log` | yes | 任务级审计。 | insert/update |
| `dbo.amazon_schema_validation_event` | yes | schema guard 记录。 | insert |

### 10.2 业务主键 / 幂等键

首版建议：

```text
business_key = marketplace_id
             + source_report_type
             + seller_sku
             + fnsku
             + asin
             + amazon_store
             + currency
             + product_size_tier
             + your_price
             + sales_price
```

理由：

1. report 没有显式业务 id 或 report period，因此不宜只用 SKU/ASIN。
2. 同一 SKU 可能同时出现 US/CA store 行，必须纳入 `amazon_store`。
3. 价格、币种、size tier 变化会影响费用预估，应形成不同 business key，避免覆盖历史费用口径。
4. 后续如果引入 report requested_at / report date 作为 business date，可考虑把业务日期纳入 key，并相应调整文档和 migration。

风险：如果同一 SKU/ASIN/store/price/size tier 在同一文件出现多条完全相同费用预估行，business key 会重复。dry-run 必须检测重复 business key；如果重复 key 对应 raw row 完全一致，可考虑 skip duplicate；如果内容不同，必须 requires_review。

### 10.3 Migration 计划

| 变更 | 原因 | Migration | 当前状态 |
|---|---|---|---|
| 新增 `source_row_index INT NULL` | 源文件行级追溯和冲突排查。 | `009_add_fba_fee_preview_business_key.sql` | executed; 4/4 batches |
| 新增 `business_key_hash NVARCHAR(100) NULL` | 支持稳定 MERGE/upsert 幂等。 | `009_add_fba_fee_preview_business_key.sql` | executed; 4/4 batches |
| 新增唯一过滤索引 `UX_amazon_fba_fee_preview_business_key_hash` | 防止重复插入同一费用预估行。 | `009_add_fba_fee_preview_business_key.sql` | executed; 4/4 batches |

`database_current_schema_spec.md` 已根据 `after_009_fba_fee_preview_business_key` live schema 同步 `source_row_index`、`business_key_hash` 和唯一过滤索引。

## 11. Schema guard 规则

### 11.1 Expected fields

首版 expected fields 固定为当前观察到的 31 个字段。缺失 required fields 时：

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

1. `seller_sku`、`fnsku`、`asin` 三者同时为空。
2. `amazon_store` 为空。
3. `currency` 为空但任一金额字段非空。
4. `estimated_fee_total`、`estimated_referral_fee_per_unit`、`expected_fulfillment_fee_per_unit` 无法解析。
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
python scripts/ingest_fba_fee_preview_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_fba_fee_preview_report.py --marketplace-id ATVPDKIKX0DER --execute
```

可选参数：

```text
--raw-file explicit/path/to/report.txt
--report-id optional_report_id
```

## 14. 相关代码路径

已新增：

```text
scripts/ingest_fba_fee_preview_report.py
src/seller_data_pipeline/ingestion/fba_fee_preview_table_mapping.py
src/seller_data_pipeline/ingestion/fba_fee_preview_ingestion_dry_run.py
src/seller_data_pipeline/ingestion/fba_fee_preview_ingestion.py
src/seller_data_pipeline/db/repositories/fba_fee_preview_repo.py
```

已存在 parser：

```text
src/seller_data_pipeline/parsers/amazon/fba_estimated_fees_parser.py
```

已新增测试：

```text
tests/unit/ingestion/test_fba_fee_preview_table_mapping.py
tests/unit/ingestion/test_fba_fee_preview_ingestion_dry_run.py
tests/unit/db/test_fba_fee_preview_repo.py
```

## 15. 验收标准

第一版功能完成必须满足：

1. `009_add_fba_fee_preview_business_key.sql` dry-run batch 数正常。
2. `009` 在 Azure SQL 执行成功。
3. `export_database_schema_spec.py --output-prefix after_009_fba_fee_preview_business_key --include-row-counts` 导出成功。
4. `database_current_schema_spec.md` 记录真实新增字段和索引。
5. dry-run 成功：已验证 `prepared_rows=8 requires_review=False`。
6. 首次 `--execute` 成功：预期 inserted=8 updated=0。
7. 第二次 `--execute` 成功：预期 inserted=0 updated=8。
8. `amazon_sync_run_log` 有成功记录。
9. `amazon_schema_validation_event` 无 blocking error。
10. 单元测试通过：`PYTHONPATH=src pytest -q` -> `174 passed`。
11. `compileall` 通过。
12. 文档同步：本 feature 文档、features README、progress、current schema spec。

## 16. 当前限制与后续优化

1. 本 report 是预估费用，不是实际扣费；后续利润模型必须清楚区分 estimated fee 与 actual settlement fee。
2. 当前样例包含 US/CA store；后续需确认 `marketplace_id` 与 `amazon_store` 的业务关系，避免跨站点误聚合。
3. 当前 business key 暂未包含 report date，因为 raw report 未提供明确业务日期；后续如果能从 report request 元数据拿到稳定业务日期，应调整 key。
4. `source_raw_file_id` 可能仍为 NULL，后续应统一 raw file registry。
5. 如果 Amazon 增加更多 future fee 字段，schema guard 应先 requires_review，再更新 data_access 与 feature 文档。

## 17. 变更记录

| 日期 | 事项 | 证据 | 备注 |
|---|---|---|---|
| 2026-05-17 | 完成 FBA Fee Preview 入库功能设计第一版 | 本文档 | 随后按流程准备 009 migration。 |
| 2026-05-17 | 准备 `009_add_fba_fee_preview_business_key.sql` | `sql/migrations/009_add_fba_fee_preview_business_key.sql` | 用户已本地 dry-run / execute 并导出 live schema。 |
| 2026-05-17 | 开发 FBA Fee Preview 专用 ingestion 并完成 dry-run 验证 | `scripts/ingest_fba_fee_preview_report.py` 等 | `prepared_rows=8 requires_review=False`；待 execute 和幂等验证。 |

## 18. 弃置记录

暂无。
