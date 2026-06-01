# Feature: Promotion and Coupon Performance Ingestion

> 文档状态：Implemented; 010 executed; dry-run, Azure SQL execute and idempotency verified  
> 负责人：AI / 待定  
> 更新时间：2026-05-17  
> 功能状态：Implemented  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`

---

## 1. 功能摘要

本功能负责把 SP-API Reports 中的 Promotion / Coupon 表现数据入库，用于后续评估你常用的运营动作：百分比优惠、固定金额优惠券、Deal/Promotion、会员日/Prime Day 活动等。

目标链路：

```text
GET_PROMOTION_PERFORMANCE_REPORT
  -> dbo.amazon_promotion_performance
  -> dbo.amazon_promotion_product_performance

GET_COUPON_PERFORMANCE_REPORT
  -> dbo.amazon_coupon_performance
  -> dbo.amazon_coupon_asin
```

这组数据主要用于**活动效果分析**，例如活动曝光、销量、销售额、优惠券领取与兑换、预算消耗、ASIN 维度表现。最终利润和真实扣款仍应以 Settlement 为财务主口径；Promotion/Coupon report 用于解释运营动作是否带来增量，而不是直接替代财务结算数据。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认；用户会经常使用 Coupon、百分比折扣、固定优惠券、会员折扣与 Prime Day 等活动 |
| 数据源取样 | 已完成；Promotion 1 个 promotion / 3 个 includedProducts，Coupon 2 个 coupons / 4 个 coupon-ASIN |
| 目标表 | 已存在于 `001_create_core_tables.sql`：4 张 promotion/coupon 表 |
| Parser | 已存在：`src/seller_data_pipeline/parsers/amazon/promotion_coupon_parser.py` |
| Migration | 已执行：`010_add_promotion_coupon_business_keys.sql`，8/8 batches；live schema export `after_010_promotion_coupon_business_keys` 已生成 |
| Dry-run preview | 已开发；本地验证 prepared_rows=10 |
| Schema guard | 已开发；Promotion/Coupon JSON path guard 已接入 |
| Repository/upsert | 已开发并完成 Azure SQL execute 验证 |
| Azure SQL execute | 已完成；首次 execute sync_run_id=17，inserted=10 updated=0 |
| 幂等性验证 | 已完成；第二次 execute sync_run_id=18，inserted=0 updated=10 |
| 单元测试 | 已新增：mapping / dry-run / repo |
| 文档同步 | 本设计已完成第一版 |

功能整体状态：`Implemented`。`010` 已执行，专用 dry-run / repository / CLI 已完成，并已通过真实 Azure SQL 首次 execute 与第二次 execute 幂等性验证。

## 3. 业务目标

本功能的业务目标是把促销活动数据沉淀下来，支持后续运营分析：

1. 评估优惠券领取、兑换、预算消耗和带来的销售额。
2. 分析百分比折扣与固定金额优惠券的效果差异。
3. 分析 Prime Day / 会员日 / Deal 类活动前后曝光、销量、销售额变化。
4. 将 Promotion/Coupon 与 Ads、Sales & Traffic、Orders、Settlement 联合分析，判断活动是否带来增量而不是单纯让利。
5. 为清仓策略提供依据：优惠券是否帮助滞销 SKU 加速出清，是否值得加码或提前停止。

注意：不同 Amazon 活动类型是否出现在 `GET_PROMOTION_PERFORMANCE_REPORT` 中，以实际 report 返回为准。若某类会员专享折扣或 Prime Day 活动未出现在当前 report，后续应先更新 `docs/data_access/`，再补充对应数据源。

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 `GET_PROMOTION_PERFORMANCE_REPORT` JSON raw file。
- 读取本地已下载的 `GET_COUPON_PERFORMANCE_REPORT` JSON raw file。
- 校验 Promotion 当前观察到的 24 个 JSON path。
- 校验 Coupon 当前观察到的 23 个 JSON path。
- 解析 promotion 主记录与 includedProducts 明细。
- 解析 coupon 主记录与 coupon-ASIN 明细。
- 生成 `source_row_index`、`source_row_hash` 与 `business_key_hash`。
- 生成 DB-ready preview JSONL。
- 默认 dry-run，不写数据库。
- 显式 `--execute` 时写入 Azure SQL。
- 写入 `amazon_sync_run_log` 和 `amazon_schema_validation_event`。
- 支持重复 execute 幂等性验证。

### 4.2 本功能不包含

- 不直接计算最终利润。
- 不把 `budgetSpent`、`totalDiscount` 直接视为最终财务扣款。
- 不替代 Settlement 中的 Coupon/Deal/Promotion 费用口径。
- 不自动创建、修改或关闭 Amazon 优惠券/活动。
- 不自动调整广告预算或商品价格。
- 不处理 Ads、Orders、Settlement 等其他 report。
- 不做 Azure Container Apps Jobs 定时化。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports | `GET_PROMOTION_PERFORMANCE_REPORT` | JSON | 已取样 1 个 promotion，3 个 includedProducts | parser / ingestion / upsert 已实现并验证 | Deal/Promotion 活动表现。 |
| SP-API Reports | `GET_COUPON_PERFORMANCE_REPORT` | JSON | 已取样 2 个 coupons，4 个 coupon-ASIN | parser / ingestion / upsert 已实现并验证 | Coupon 预算、领取、兑换、折扣和销售额。 |

当前样例：

| Report | raw file | row/array count | field path count | sample doc |
|---|---|---:|---:|---|
| `GET_PROMOTION_PERFORMANCE_REPORT` | `reports/raw/amazon/ATVPDKIKX0DER/GET_PROMOTION_PERFORMANCE_REPORT/2026-05-14/112491020587.txt` | promotions=1; includedProducts=3 | 24 | `requirements_to_be_deprecated/data_samples/GET_PROMOTION_PERFORMANCE_REPORT.md` |
| `GET_COUPON_PERFORMANCE_REPORT` | `reports/raw/amazon/ATVPDKIKX0DER/GET_COUPON_PERFORMANCE_REPORT/2026-05-14/112492020587.txt` | coupons=2; coupon ASINs=4 | 23 | `requirements_to_be_deprecated/data_samples/GET_COUPON_PERFORMANCE_REPORT.md` |

## 6. 源字段结构

### 6.1 Promotion JSON paths

当前观察到的关键字段：

```text
promotions[].promotionId
promotions[].marketplaceId
promotions[].merchantId
promotions[].promotionName
promotions[].type
promotions[].status
promotions[].glanceViews
promotions[].unitsSold
promotions[].revenue
promotions[].revenueCurrencyCode
promotions[].startDateTime
promotions[].endDateTime
promotions[].createdDateTime
promotions[].lastUpdatedDateTime
promotions[].includedProducts[].asin
promotions[].includedProducts[].productName
promotions[].includedProducts[].productGlanceViews
promotions[].includedProducts[].productUnitsSold
promotions[].includedProducts[].productRevenue
promotions[].includedProducts[].productRevenueCurrencyCode
reportSpecification.reportOptions.promotionStartDateFrom
reportSpecification.reportOptions.promotionStartDateTo
```

### 6.2 Coupon JSON paths

当前观察到的关键字段：

```text
coupons[].couponId
coupons[].marketplaceId
coupons[].merchantId
coupons[].currencyCode
coupons[].name
coupons[].websiteMessage
coupons[].startDateTime
coupons[].endDateTime
coupons[].discountType
coupons[].discountAmount
coupons[].totalDiscount
coupons[].clips
coupons[].redemptions
coupons[].budget
coupons[].budgetSpent
coupons[].budgetRemaining
coupons[].budgetPercentageUsed
coupons[].sales
coupons[].asins[].asin
reportSpecification.reportOptions.couponStartDateFrom
reportSpecification.reportOptions.couponStartDateTo
```

## 7. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/sp_api/{report_type}/{marketplace_id}/{timestamp}/...` | dry-run / execute 汇总。 |
| Schema events JSONL | 同上 | 入库前字段验证结果。 |
| Preview rows | `previews/*.preview.jsonl` | 四张目标表的 DB-ready preview。 |
| Azure SQL tables | `dbo.amazon_promotion_performance` 等 4 张表 | 活动主表与商品/ASIN 明细表。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录 schema guard 结果。 |

## 8. 处理流程

建议实现为专用入口：

```text
local promotion/coupon raw files
  -> find latest raw file for each report type, or accept --raw-file explicit paths
  -> decode JSON
  -> validate expected JSON paths
  -> parse with PromotionPerformanceParser / CouponPerformanceParser
  -> flatten parent and nested records into four target row sets
  -> compute source_row_index per target table logical row
  -> compute source_row_hash from source raw object
  -> compute business_key_hash for each target row
  -> detect duplicate business keys within the same batch
  -> write DB-ready preview JSONL
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE rows into four target tables by business_key_hash
  -> insert schema validation event(s)
  -> update amazon_sync_run_log final status
  -> commit transaction
```

关键行为：

1. 默认 dry-run，不写数据库。
2. 只有显式 `--execute` 才允许写 Azure SQL。
3. 任一 report `requires_review=True` 时必须阻断 execute。
4. 写库必须通过 `get_connection()`，让 Azure SQL connection retry + `SELECT 1` warm-up 生效。
5. 同一 batch 内 business key 冲突但 payload 不一致时，必须 requires_review 并阻断 execute。

## 9. 字段映射

### 9.1 Promotion 主表

目标表：`dbo.amazon_promotion_performance`

| 源字段 | 目标字段 | 说明 |
|---|---|---|
| `promotions[].marketplaceId` | `marketplace_id` | 缺失时可 fallback 到 reportSpecification marketplace。 |
| `promotions[].promotionId` | `promotion_id` | Promotion/Deal ID。 |
| `promotions[].merchantId` | `merchant_id` | Seller merchant id。 |
| `promotions[].promotionName` | `promotion_name` | 活动名。 |
| `promotions[].type` | `promotion_type` | 样例为 `BEST_DEAL`。 |
| `promotions[].status` | `status` | 活动状态。 |
| `promotions[].glanceViews` | `glance_views` | 活动总体浏览。 |
| `promotions[].unitsSold` | `units_sold` | 活动总体销量。 |
| `promotions[].revenue` | `revenue` | 活动总体销售额，运营口径。 |
| `promotions[].revenueCurrencyCode` | `revenue_currency_code` | 币种。 |
| `promotions[].startDateTime` | `start_date_time_raw` | 原始时间字符串。 |
| `promotions[].endDateTime` | `end_date_time_raw` | 原始时间字符串。 |
| `promotions[].createdDateTime` | `created_date_time_raw` | 原始时间字符串。 |
| `promotions[].lastUpdatedDateTime` | `last_updated_date_time_raw` | 原始时间字符串。 |

Business key 建议：

```text
source_report_type + marketplace_id + promotion_id + merchant_id + start_date_time_raw + end_date_time_raw
```

### 9.2 Promotion 商品明细表

目标表：`dbo.amazon_promotion_product_performance`

| 源字段 | 目标字段 | 说明 |
|---|---|---|
| parent promotion fields | `promotion_id` / `merchant_id` / `promotion_name` / `promotion_type` / `status` | 从 parent promotion 继承。 |
| `includedProducts[].asin` | `asin` | 活动商品 ASIN。 |
| `includedProducts[].productName` | `product_name` | 商品名。 |
| `includedProducts[].productGlanceViews` | `product_glance_views` | 商品维度浏览。 |
| `includedProducts[].productUnitsSold` | `product_units_sold` | 商品维度销量。 |
| `includedProducts[].productRevenue` | `product_revenue` | 商品维度销售额。 |
| `includedProducts[].productRevenueCurrencyCode` | `product_revenue_currency_code` | 币种。 |

Business key 建议：

```text
source_report_type + marketplace_id + promotion_id + merchant_id + asin
```

### 9.3 Coupon 主表

目标表：`dbo.amazon_coupon_performance`

| 源字段 | 目标字段 | 说明 |
|---|---|---|
| `coupons[].marketplaceId` | `marketplace_id` | marketplace。 |
| `coupons[].couponId` | `coupon_id` | Coupon ID。 |
| `coupons[].merchantId` | `merchant_id` | Seller merchant id。 |
| `coupons[].currencyCode` | `currency_code` | 币种。 |
| `coupons[].name` | `name` | Coupon 名称。 |
| `coupons[].websiteMessage` | `website_message` | 前台文案。 |
| `coupons[].startDateTime` | `start_date_time_raw` | 原始时间字符串。 |
| `coupons[].endDateTime` | `end_date_time_raw` | 原始时间字符串。 |
| `coupons[].discountType` | `discount_type` | 样例含固定金额、百分比折扣。 |
| `coupons[].discountAmount` | `discount_amount` | 折扣值。 |
| `coupons[].totalDiscount` | `total_discount` | 总折扣，运营口径。 |
| `coupons[].clips` | `clips` | 领取数。 |
| `coupons[].redemptions` | `redemptions` | 兑换数。 |
| `coupons[].budget` | `budget` | 预算。 |
| `coupons[].budgetSpent` | `budget_spent` | 已消耗预算，运营口径。 |
| `coupons[].budgetRemaining` | `budget_remaining` | 剩余预算。 |
| `coupons[].budgetPercentageUsed` | `budget_percentage_used` | 预算使用率。 |
| `coupons[].sales` | `sales` | Coupon 带来的销售额，运营口径。 |

Business key 建议：

```text
source_report_type + marketplace_id + coupon_id + merchant_id + start_date_time_raw + end_date_time_raw
```

### 9.4 Coupon ASIN 明细表

目标表：`dbo.amazon_coupon_asin`

| 源字段 | 目标字段 | 说明 |
|---|---|---|
| parent coupon fields | `coupon_id` / `merchant_id` / `coupon_name` / `currency_code` / `start_date_time_raw` / `end_date_time_raw` | 从 parent coupon 继承。 |
| `coupons[].asins[].asin` | `asin` | Coupon 关联 ASIN。 |

Business key 建议：

```text
source_report_type + marketplace_id + coupon_id + merchant_id + asin
```

## 10. 数据库结构变更

当前 4 张目标表已存在，但缺少稳定 upsert 需要的 `business_key_hash` 和逻辑行号字段。已准备 migration：

```text
sql/migrations/010_add_promotion_coupon_business_keys.sql
```

该 migration 将为以下表增加：

```text
source_row_index INT NULL
business_key_hash NVARCHAR(100) NULL
```

并创建唯一过滤索引：

```text
UX_amazon_promotion_performance_business_key_hash
UX_amazon_promotion_product_performance_business_key_hash
UX_amazon_coupon_performance_business_key_hash
UX_amazon_coupon_asin_business_key_hash
```

`source_row_index` 在 JSON report 中表示目标表内的逻辑记录序号，而不是 flat file 的物理行号。

## 11. 审计与可追溯性

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

## 12. 验收标准

### 12.1 Migration 验收

```powershell
python scripts/run_sql_migration.py --file sql/migrations/010_add_promotion_coupon_business_keys.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/010_add_promotion_coupon_business_keys.sql
python scripts/export_database_schema_spec.py --output-prefix after_010_promotion_coupon_business_keys --include-row-counts
```

预期：

```text
010 dry-run: 8 executable batches
010 execute: 8/8 batches
live schema export 成功
```

### 12.2 Ingestion 验收

建议命令：

```powershell
python scripts/ingest_promotion_coupon_reports.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_promotion_coupon_reports.py --marketplace-id ATVPDKIKX0DER --execute
python scripts/ingest_promotion_coupon_reports.py --marketplace-id ATVPDKIKX0DER --execute
```

预期：

```text
dry-run: requires_review=False
首次 execute: inserted > 0, updated=0
第二次 execute: inserted=0, updated=首次 inserted 行数
```

基于当前样例，预期目标行数约为：

```text
amazon_promotion_performance: 1
amazon_promotion_product_performance: 3
amazon_coupon_performance: 2
amazon_coupon_asin: 4
合计：10
```

## 13. 相关代码路径

已存在：

```text
src/seller_data_pipeline/parsers/amazon/promotion_coupon_parser.py
```

待新增：

```text
scripts/ingest_promotion_coupon_reports.py
src/seller_data_pipeline/ingestion/promotion_coupon_table_mapping.py
src/seller_data_pipeline/ingestion/promotion_coupon_ingestion_dry_run.py
src/seller_data_pipeline/ingestion/promotion_coupon_ingestion.py
src/seller_data_pipeline/db/repositories/promotion_coupon_repo.py
tests/unit/ingestion/test_promotion_coupon_table_mapping.py
tests/unit/ingestion/test_promotion_coupon_ingestion_dry_run.py
tests/unit/db/test_promotion_coupon_repo.py
```

## 14. 弃置记录

| 日期 | 方案 | 弃置原因 | 替代方案 |
|---|---|---|---|
| 2026-05-17 | 直接把 Promotion/Coupon 折扣当成最终成本 | 运营报表口径不等于财务结算口径，可能与 Settlement 不一致 | Promotion/Coupon 用于活动效果分析；最终利润以 Settlement 为主口径。 |
| 2026-05-17 | 继续拖延 Promotion/Coupon 到利润核算后 | 用户会高频使用优惠券、折扣、会员日/Prime Day 活动，促销效果是日常运营核心数据 | 在利润核算前先补 Promotion/Coupon 入库。 |


## 16. 当前开发验证结果

本轮已实现专用入口：

```text
scripts/ingest_promotion_coupon_reports.py
```

最终验收结果：

```text
dry-run: prepared_rows=10 requires_review=False
首次 execute: sync_run_id=17, attempted=10 inserted=10 updated=0 written=10 skipped=0
第二次 execute: sync_run_id=18, attempted=10 inserted=0 updated=10 written=10 skipped=0

amazon_promotion_performance: 1 row
amazon_promotion_product_performance: 3 rows
amazon_coupon_performance: 2 rows
amazon_coupon_asin: 4 rows
```

本功能已完成当前阶段验收。后续利润/促销复盘功能应把本数据作为活动效果口径，最终财务扣款仍以 Settlement 为主口径。
