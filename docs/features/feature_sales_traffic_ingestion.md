# Feature: Sales & Traffic Report Ingestion

> 文档状态：Implemented v1.1; Azure verification pending  
> 负责人：AI / 待定  
> 更新时间：2026-08-08  
> 功能状态：Implemented  
> 相关数据接入文档：`docs/data_access/sp_api_reports_catalog.md`  
> 相关数据库 spec：`docs/database/database_current_schema_spec.md`  
> 相关 ADR：`docs/adr/ADR-013-schema-guard-compatibility-policy.md`

---

## 1. 功能摘要

本功能负责把 SP-API Reports 的 `GET_SALES_AND_TRAFFIC_REPORT` JSON raw file 转换为 Azure SQL 中两张 normalized 表：

```text
salesAndTrafficByDate -> dbo.amazon_sales_traffic_daily
salesAndTrafficByAsin -> dbo.amazon_sales_traffic_asin_daily
```

它是 Ads、Listing、Inventory 之后的下一条 SP-API normalized ingestion 主线，用于沉淀店铺整体销售额、订单数、销量、退款、sessions、page views、Buy Box、转化率，以及 ASIN 维度销售/流量表现。

第一版只处理本地已下载 raw report 的解析、schema guard、dry-run preview、Azure SQL MERGE/upsert 和幂等性验证；不负责自动提交/下载 report，不负责利润核算，不负责周报生成，也不负责广告归因合并。

## 2. 功能状态

| 项目 | 状态 |
|---|---|
| 需求确认 | 已确认 |
| 数据源取样 | 已完成，当前样例为 JSON，`salesAndTrafficByDate` 6 行，`salesAndTrafficByAsin` 1 行 |
| 目标表 | 已存在于 `001_create_core_tables.sql` |
| Parser | 已实现 |
| Dry-run preview | 已实现并通过 |
| Schema guard | v1.1 robustness 已实现：additive drift non-blocking，6 个 required raw path fail closed；Azure 重跑待验证 |
| Repository/upsert | 已实现并通过 |
| 005 migration | 已在 Azure SQL 执行成功，5/5 batches；live schema export 已完成 |
| Azure SQL execute | 已完成，sync_run_id=7，inserted=7 updated=0 |
| 幂等性验证 | 已完成，sync_run_id=8，inserted=0 updated=7 |
| 单元测试 | 已新增并通过 |
| 文档同步 | 已同步为 Implemented |

功能整体状态：`Implemented`。当前已完成设计、`005_add_sales_traffic_business_key_hashes.sql`、live schema export、专用 CLI、mapping、dry-run、execute orchestration、repository、单元测试、首次真实 execute 和第二次 execute 幂等性验证。

## 3. 业务目标

销售与流量数据是后续运营分析的核心事实数据之一。本功能目标是每天或按取样窗口沉淀以下指标：

1. 店铺日期维度销售额、销量、订单数、退款、发货销售额。
2. 店铺日期维度 sessions、page views、Buy Box、转化率。
3. ASIN 维度销售、订单、销量、sessions、page views、转化率。
4. 支持后续与 Ads 花费、Listing 状态、Inventory 库存、Settlement 结算关联，用于利润核算、广告效果判断、清仓速度判断和周报/月报。

本功能不直接计算利润。利润应由后续 `feature_profit_calculation.md` 基于 Sales/Settlement/Ads/SKU cost 等数据独立设计。

## 4. 范围与非范围

### 4.1 本功能包含

- 读取本地已下载的 `GET_SALES_AND_TRAFFIC_REPORT` JSON raw file。
- 校验 JSON 顶层结构、`reportSpecification`、`salesAndTrafficByDate`、`salesAndTrafficByAsin`。
- 对当前观察到的 94 个 JSON path 做 expected schema 检查。
- 把 `salesAndTrafficByDate[]` 映射到 `dbo.amazon_sales_traffic_daily`。
- 把 `salesAndTrafficByAsin[]` 映射到 `dbo.amazon_sales_traffic_asin_daily`。
- 生成 dry-run preview JSONL。
- 默认 dry-run，不写数据库。
- 显式 `--execute` 时写入 Azure SQL。
- 写入 `amazon_sync_run_log` 和 `amazon_schema_validation_event`。
- 支持重复 execute 幂等性验证。
- 保留完整 `raw_data` 和 `source_row_hash` 便于追溯。

### 4.2 本功能不包含

- 不负责提交/下载 SP-API report request。
- 不负责订单明细；订单明细来自 `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL`。
- 不负责结算入账；结算来自 `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2`。
- 不负责广告归因；广告来自 Amazon Ads SP reports。
- 不负责利润核算、库存周转、清仓建议、周报/月报生成。
- 不负责 Azure Container Apps Jobs 定时化；第一版仍先完成本地 CLI + Azure SQL 写库闭环。

## 5. 输入数据

| 来源系统 | Report/API/文件 | 文件格式 | 当前取样状态 | 当前解析状态 | 备注 |
|---|---|---|---|---|---|
| SP-API Reports | `GET_SALES_AND_TRAFFIC_REPORT` | JSON | 已取样，94 个 observed path | 已新增 dry-run / repository / CLI，真实 execute 和幂等性验证已完成 | 包含日期维度和 ASIN 维度。 |

当前样例记录：

| 项目 | 当前值 |
|---|---|
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_SALES_AND_TRAFFIC_REPORT/2026-05-14/112445020587.txt` |
| encoding | `utf-8-sig` |
| file_format | `json` |
| `salesAndTrafficByDate` row_count | `6` |
| `salesAndTrafficByAsin` row_count | `1` |
| observed path count | `94` |
| sample doc | `requirements_to_be_deprecated/data_samples/GET_SALES_AND_TRAFFIC_REPORT.md` |

当前 raw 路径约定：

```text
reports/raw/amazon/{marketplace_id}/{report_type}/{date}/{report_id}.txt
```

## 6. Report options 与粒度约束

当前样例中 `reportSpecification.reportOptions` 包含：

| path | 当前样例 | 第一版处理 |
|---|---|---|
| `dateGranularity` | `DAY` | 第一版只支持 `DAY`，其他值先 `requires_review=True`。 |
| `asinGranularity` | 当前样例为 PARENT 粒度 | 第一版支持当前样例粒度；如后续切到 CHILD，应先确认 `childAsin` 字段和表映射。 |

第一版建议严格控制粒度，不要在同一张 daily 表里混写不同日期粒度。若后续需要 WEEK/MONTH，应新增或明确设计聚合表，而不是直接塞入 `amazon_sales_traffic_daily`。

## 7. 输出结果

| 输出类型 | 输出位置 | 用途 |
|---|---|---|
| Runtime summary | `runtime/ingestion/sp_api/GET_SALES_AND_TRAFFIC_REPORT/{marketplace_id}/{timestamp}/...` | 本次 dry-run / execute 汇总。 |
| Schema events JSONL | 同上 | 入库前字段验证结果。 |
| Preview rows by date | `previews/amazon_sales_traffic_daily.preview.jsonl` | 日期维度 DB-ready preview。 |
| Preview rows by ASIN | `previews/amazon_sales_traffic_asin_daily.preview.jsonl` | ASIN 维度 DB-ready preview。 |
| Azure SQL table | `dbo.amazon_sales_traffic_daily` | 日期维度销售与流量日快照。 |
| Azure SQL table | `dbo.amazon_sales_traffic_asin_daily` | ASIN 维度销售与流量快照。 |
| Audit table | `dbo.amazon_sync_run_log` | 记录本次 execute 任务。 |
| Validation table | `dbo.amazon_schema_validation_event` | 记录本 report 的 schema guard 结果。 |

## 8. 处理流程

按 Listing / Inventory 已跑通的专用入口模式实现，不急于抽象通用 SP-API ingestion 入口：

```text
local GET_SALES_AND_TRAFFIC_REPORT JSON file
  -> find latest raw file for marketplace/report_type, or accept --raw-file explicit path
  -> decode JSON content
  -> validate reportSpecification and reportOptions
  -> collect observed JSON paths
  -> compare with expected sales traffic schema
  -> if requires_review=True: block database write
  -> parse salesAndTrafficByDate[] into SalesTrafficDailyRecord
  -> parse salesAndTrafficByAsin[] into SalesTrafficAsinDailyRecord
  -> compute source_row_hash for each logical row
  -> compute business_key_hash for each target table row
  -> write DB-ready preview JSONL files
  -> if --execute not set: stop after dry-run
  -> insert running row into amazon_sync_run_log
  -> MERGE daily rows into amazon_sales_traffic_daily by business_key_hash
  -> MERGE asin rows into amazon_sales_traffic_asin_daily by business_key_hash
  -> insert schema validation event
  -> update amazon_sync_run_log final status
  -> commit transaction
```

关键行为：

1. 默认模式必须是 dry-run，不写数据库。
2. 只有显式传入 `--execute` 才允许连接 Azure SQL 并写库。
3. 如果 schema guard 产生 `requires_review=True`，真实写库必须被阻断。
4. 写库必须通过 `get_connection()`，让 Azure SQL connection retry + `SELECT 1` warm-up 先完成。
5. 两张目标表应在同一事务内写入；其中任一表失败时整体 rollback。
6. 不使用 `source_row_hash` 作为业务幂等键；必须使用目标表各自的 `business_key_hash`。

## 9. 字段映射

### 9.1 `salesAndTrafficByDate[]` -> `amazon_sales_traffic_daily`

| 源 JSON path | 目标字段 | 类型 | 说明 |
|---|---|---|---|
| `reportSpecification.marketplaceIds[]` / CLI | `marketplace_id` | string | 第一版以 CLI `--marketplace-id` 为主，JSON 中 marketplaceIds 用于一致性校验。 |
| `salesAndTrafficByDate[].date` | `report_date` | date | 日期维度主日期。 |
| `reportSpecification.reportOptions.dateGranularity` | `date_granularity` | string | 第一版应为 `DAY`。 |
| `reportSpecification.reportOptions.asinGranularity` | `asin_granularity` | string | 保留 report option。 |
| `salesAndTrafficByDate[].salesByDate.orderedProductSales.amount` | `ordered_product_sales_amount` | decimal | 订单商品销售额。 |
| `salesAndTrafficByDate[].salesByDate.orderedProductSales.currencyCode` | `ordered_product_sales_currency` | string | 销售额币种。 |
| `salesAndTrafficByDate[].salesByDate.orderedProductSalesB2B.amount` | `ordered_product_sales_b2b_amount` | decimal | B2B 销售额。 |
| `salesAndTrafficByDate[].salesByDate.orderedProductSalesB2B.currencyCode` | `ordered_product_sales_b2b_currency` | string | B2B 销售额币种。 |
| `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItem.amount` | `average_sales_per_order_item_amount` | decimal | 每订单商品平均销售额。 |
| `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItem.currencyCode` | `average_sales_per_order_item_currency` | string | 币种。 |
| `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItemB2B.amount` | `average_sales_per_order_item_b2b_amount` | decimal | B2B 每订单商品平均销售额。 |
| `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItemB2B.currencyCode` | `average_sales_per_order_item_b2b_currency` | string | 币种。 |
| `salesAndTrafficByDate[].salesByDate.averageUnitsPerOrderItem` | `average_units_per_order_item` | decimal | 每订单商品平均件数。 |
| `salesAndTrafficByDate[].salesByDate.averageUnitsPerOrderItemB2B` | `average_units_per_order_item_b2b` | decimal | B2B 每订单商品平均件数。 |
| `salesAndTrafficByDate[].salesByDate.averageSellingPrice.amount` | `average_selling_price_amount` | decimal | 平均售价。 |
| `salesAndTrafficByDate[].salesByDate.averageSellingPrice.currencyCode` | `average_selling_price_currency` | string | 币种。 |
| `salesAndTrafficByDate[].salesByDate.averageSellingPriceB2B.amount` | `average_selling_price_b2b_amount` | decimal | B2B 平均售价。 |
| `salesAndTrafficByDate[].salesByDate.averageSellingPriceB2B.currencyCode` | `average_selling_price_b2b_currency` | string | 币种。 |
| `salesAndTrafficByDate[].salesByDate.unitsOrdered` | `units_ordered` | int | 已订购件数。 |
| `salesAndTrafficByDate[].salesByDate.unitsOrderedB2B` | `units_ordered_b2b` | int | B2B 已订购件数。 |
| `salesAndTrafficByDate[].salesByDate.totalOrderItems` | `total_order_items` | int | 订单商品数。 |
| `salesAndTrafficByDate[].salesByDate.totalOrderItemsB2B` | `total_order_items_b2b` | int | B2B 订单商品数。 |
| `salesAndTrafficByDate[].salesByDate.unitsRefunded` | `units_refunded` | int | 退款件数。 |
| `salesAndTrafficByDate[].salesByDate.refundRate` | `refund_rate` | decimal | 退款率。 |
| `salesAndTrafficByDate[].salesByDate.claimsGranted` | `claims_granted` | int | A-to-z claims granted。 |
| `salesAndTrafficByDate[].salesByDate.claimsAmount.amount` | `claims_amount` | decimal | claim 金额。 |
| `salesAndTrafficByDate[].salesByDate.claimsAmount.currencyCode` | `claims_amount_currency` | string | claim 币种。 |
| `salesAndTrafficByDate[].salesByDate.shippedProductSales.amount` | `shipped_product_sales_amount` | decimal | 已发货商品销售额。 |
| `salesAndTrafficByDate[].salesByDate.shippedProductSales.currencyCode` | `shipped_product_sales_currency` | string | 币种。 |
| `salesAndTrafficByDate[].salesByDate.unitsShipped` | `units_shipped` | int | 已发货件数。 |
| `salesAndTrafficByDate[].salesByDate.ordersShipped` | `orders_shipped` | int | 已发货订单数。 |
| `salesAndTrafficByDate[].trafficByDate.browserPageViews` | `browser_page_views` | int | 浏览器 page views。 |
| `salesAndTrafficByDate[].trafficByDate.mobileAppPageViews` | `mobile_app_page_views` | int | App page views。 |
| `salesAndTrafficByDate[].trafficByDate.pageViews` | `page_views` | int | 总 page views。 |
| `salesAndTrafficByDate[].trafficByDate.browserSessions` | `browser_sessions` | int | 浏览器 sessions。 |
| `salesAndTrafficByDate[].trafficByDate.mobileAppSessions` | `mobile_app_sessions` | int | App sessions。 |
| `salesAndTrafficByDate[].trafficByDate.sessions` | `sessions` | int | 总 sessions。 |
| `salesAndTrafficByDate[].trafficByDate.buyBoxPercentage` | `buy_box_percentage` | decimal | Buy Box 百分比。 |
| `salesAndTrafficByDate[].trafficByDate.orderItemSessionPercentage` | `order_item_session_percentage` | decimal | 订单商品/session 转化率。 |
| `salesAndTrafficByDate[].trafficByDate.unitSessionPercentage` | `unit_session_percentage` | decimal | unit/session 转化率。 |
| `salesAndTrafficByDate[].trafficByDate.averageOfferCount` | `average_offer_count` | decimal | 平均 offer 数。 |
| `salesAndTrafficByDate[].trafficByDate.averageParentItems` | `average_parent_items` | decimal | 平均 parent items。 |
| `salesAndTrafficByDate[].trafficByDate.feedbackReceived` | `feedback_received` | int | 收到 feedback 数。 |
| `salesAndTrafficByDate[].trafficByDate.negativeFeedbackReceived` | `negative_feedback_received` | int | 负面 feedback 数。 |
| `salesAndTrafficByDate[].trafficByDate.receivedNegativeFeedbackRate` | `received_negative_feedback_rate` | decimal | 负面 feedback 比率。 |
| source metadata | `source_*`, `source_row_hash`, `raw_data` | mixed | 按统一 ingestion 审计字段写入。 |

### 9.2 `salesAndTrafficByAsin[]` -> `amazon_sales_traffic_asin_daily`

| 源 JSON path | 目标字段 | 类型 | 说明 |
|---|---|---|---|
| `reportSpecification.marketplaceIds[]` / CLI | `marketplace_id` | string | 第一版以 CLI `--marketplace-id` 为主。 |
| `reportSpecification.dataStartTime` | `report_start_date` | date | ASIN 维度覆盖窗口开始日期。 |
| `reportSpecification.dataEndTime` | `report_end_date` | date | ASIN 维度覆盖窗口结束日期。 |
| `salesAndTrafficByAsin[].parentAsin` | `parent_asin` | string | Parent ASIN。 |
| `salesAndTrafficByAsin[].childAsin` | `child_asin` | string | 当前样例可能没有；如后续 CHILD 粒度出现，应映射。 |
| `reportSpecification.reportOptions.dateGranularity` | `date_granularity` | string | 保留 report option。 |
| `reportSpecification.reportOptions.asinGranularity` | `asin_granularity` | string | 当前样例为 Parent 粒度。 |
| `salesAndTrafficByAsin[].salesByAsin.orderedProductSales.amount` | `ordered_product_sales_amount` | decimal | ASIN 销售额。 |
| `salesAndTrafficByAsin[].salesByAsin.orderedProductSales.currencyCode` | `ordered_product_sales_currency` | string | 币种。 |
| `salesAndTrafficByAsin[].salesByAsin.orderedProductSalesB2B.amount` | `ordered_product_sales_b2b_amount` | decimal | B2B ASIN 销售额。 |
| `salesAndTrafficByAsin[].salesByAsin.orderedProductSalesB2B.currencyCode` | `ordered_product_sales_b2b_currency` | string | 币种。 |
| `salesAndTrafficByAsin[].salesByAsin.unitsOrdered` | `units_ordered` | int | ASIN 件数。 |
| `salesAndTrafficByAsin[].salesByAsin.unitsOrderedB2B` | `units_ordered_b2b` | int | B2B 件数。 |
| `salesAndTrafficByAsin[].salesByAsin.totalOrderItems` | `total_order_items` | int | ASIN 订单商品数。 |
| `salesAndTrafficByAsin[].salesByAsin.totalOrderItemsB2B` | `total_order_items_b2b` | int | B2B 订单商品数。 |
| `salesAndTrafficByAsin[].trafficByAsin.browserPageViews` | `browser_page_views` | int | 浏览器 page views。 |
| `salesAndTrafficByAsin[].trafficByAsin.browserPageViewsB2B` | `browser_page_views_b2b` | int | B2B 浏览器 page views。 |
| `salesAndTrafficByAsin[].trafficByAsin.browserPageViewsPercentage` | `browser_page_views_percentage` | decimal | 浏览器 page views 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.browserPageViewsPercentageB2B` | `browser_page_views_percentage_b2b` | decimal | B2B 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViews` | `mobile_app_page_views` | int | App page views。 |
| `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsB2B` | `mobile_app_page_views_b2b` | int | B2B App page views。 |
| `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsPercentage` | `mobile_app_page_views_percentage` | decimal | App page views 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsPercentageB2B` | `mobile_app_page_views_percentage_b2b` | decimal | B2B 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.pageViews` | `page_views` | int | 总 page views。 |
| `salesAndTrafficByAsin[].trafficByAsin.pageViewsB2B` | `page_views_b2b` | int | B2B page views。 |
| `salesAndTrafficByAsin[].trafficByAsin.pageViewsPercentage` | `page_views_percentage` | decimal | page views 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.pageViewsPercentageB2B` | `page_views_percentage_b2b` | decimal | B2B page views 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.browserSessions` | `browser_sessions` | int | 浏览器 sessions。 |
| `salesAndTrafficByAsin[].trafficByAsin.browserSessionsB2B` | `browser_sessions_b2b` | int | B2B 浏览器 sessions。 |
| `salesAndTrafficByAsin[].trafficByAsin.browserSessionPercentage` | `browser_session_percentage` | decimal | 浏览器 session 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.browserSessionPercentageB2B` | `browser_session_percentage_b2b` | decimal | B2B 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessions` | `mobile_app_sessions` | int | App sessions。 |
| `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionsB2B` | `mobile_app_sessions_b2b` | int | B2B App sessions。 |
| `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionPercentage` | `mobile_app_session_percentage` | decimal | App session 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionPercentageB2B` | `mobile_app_session_percentage_b2b` | decimal | B2B 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.sessions` | `sessions` | int | 总 sessions。 |
| `salesAndTrafficByAsin[].trafficByAsin.sessionsB2B` | `sessions_b2b` | int | B2B sessions。 |
| `salesAndTrafficByAsin[].trafficByAsin.sessionPercentage` | `session_percentage` | decimal | session 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.sessionPercentageB2B` | `session_percentage_b2b` | decimal | B2B session 占比。 |
| `salesAndTrafficByAsin[].trafficByAsin.buyBoxPercentage` | `buy_box_percentage` | decimal | Buy Box 百分比。 |
| `salesAndTrafficByAsin[].trafficByAsin.buyBoxPercentageB2B` | `buy_box_percentage_b2b` | decimal | B2B Buy Box 百分比。 |
| `salesAndTrafficByAsin[].trafficByAsin.unitSessionPercentage` | `unit_session_percentage` | decimal | unit/session 转化率。 |
| `salesAndTrafficByAsin[].trafficByAsin.unitSessionPercentageB2B` | `unit_session_percentage_b2b` | decimal | B2B unit/session 转化率。 |
| source metadata | `source_*`, `source_row_hash`, `raw_data` | mixed | 按统一 ingestion 审计字段写入。 |

## 10. 目标数据表设计

### 10.1 涉及表

| 表 | 当前是否存在 | 用途 | 写入方式 |
|---|---|---|---|
| `dbo.amazon_sales_traffic_daily` | yes | 日期维度销售与流量 | MERGE/upsert 已验证 |
| `dbo.amazon_sales_traffic_asin_daily` | yes | ASIN 维度销售与流量 | MERGE/upsert 已验证 |
| `dbo.amazon_sync_run_log` | yes | 任务审计 | insert then update |
| `dbo.amazon_schema_validation_event` | yes | schema guard 审计 | append-only insert |
| `dbo.amazon_raw_report_file` | yes | raw file registry | 后续应写入；本功能首版可先保存 path/hash |

### 10.2 业务主键 / 幂等键

建议两张表各自使用 `business_key_hash`。

日期维度：

```text
business_key = marketplace_id + report_date + date_granularity
business_key_hash = sha256(canonical JSON of business_key)
```

说明：

- 第一版只支持 `dateGranularity=DAY`，所以 `report_date` 是天然日维度主键。
- `asinGranularity` 不建议进入日期表业务键，否则相同日期在不同 ASIN 粒度请求下可能重复生成店铺整体日汇总。第一版应在 schema guard 层限制 report options，而不是允许同一天多版本混写。

ASIN 维度：

```text
business_key = marketplace_id + report_start_date + report_end_date + asin_granularity + parent_asin + child_asin
business_key_hash = sha256(canonical JSON of business_key)
```

说明：

- `salesAndTrafficByAsin[]` 当前样例不含单日字段，代表整个 report date range 内的 ASIN 维度汇总。
- `parent_asin` 是当前样例主键字段。
- 如果后续 `asinGranularity=CHILD` 且出现 `childAsin`，需要纳入 business key。

### 10.3 新 migration 需求

当前两张表已存在，但缺少 `business_key_hash` 字段。根据 Ads / Listing / Inventory 已验证模式，建议新增：

| 变化 | 原因 | migration 文件 | 状态 |
|---|---|---|---|
| 新增 `amazon_sales_traffic_daily.business_key_hash NVARCHAR(100) NULL` | 支持稳定 MERGE/upsert 幂等键 | `005_add_sales_traffic_business_key_hashes.sql` | executed, 5/5 batches |
| 新增 `UX_amazon_sales_traffic_daily_business_key_hash` | 防止同一日期维度业务键重复插入 | `005_add_sales_traffic_business_key_hashes.sql` | executed, 5/5 batches |
| 新增 `amazon_sales_traffic_asin_daily.business_key_hash NVARCHAR(100) NULL` | 支持 ASIN 维度稳定 MERGE/upsert 幂等键 | `005_add_sales_traffic_business_key_hashes.sql` | executed, 5/5 batches |
| 新增 `UX_amazon_sales_traffic_asin_daily_business_key_hash` | 防止同一 ASIN 维度业务键重复插入 | `005_add_sales_traffic_business_key_hashes.sql` | executed, 5/5 batches |

字段先允许 `NULL`，索引使用 filtered unique index：

```sql
WHERE business_key_hash IS NOT NULL
```

这样即使未来表中已有历史数据，也不会因为旧行缺少 business key 而导致 migration 失败；repository 写入时仍然必须要求新行生成非空 `business_key_hash`。

## 11. 幂等性设计

重复执行同一批 Sales & Traffic raw file 应该安全。

当前样例预期行数：

```text
amazon_sales_traffic_daily: 6 rows
amazon_sales_traffic_asin_daily: 1 row
```

预期验收：

```text
第一次 execute:
  daily attempted=6 inserted=6 updated=0
  asin attempted=1 inserted=1 updated=0

第二次 execute:
  daily attempted=6 inserted=0 updated=6
  asin attempted=1 inserted=0 updated=1

目标表总行数保持：daily=6, asin=1
```

实际验收结果：

```text
Dry-run: prepared_rows=7 requires_review=False
首次 execute: sync_run_id=7, attempted=7 inserted=7 updated=0 written=7 skipped=0
  amazon_sales_traffic_daily: attempted=6 inserted=6 updated=0 skipped=0
  amazon_sales_traffic_asin_daily: attempted=1 inserted=1 updated=0 skipped=0
第二次 execute: sync_run_id=8, attempted=7 inserted=0 updated=7 written=7 skipped=0
  amazon_sales_traffic_daily: attempted=6 inserted=0 updated=6 skipped=0
  amazon_sales_traffic_asin_daily: attempted=1 inserted=0 updated=1 skipped=0
```

如果后续 repository 增加“完全相同内容不更新”的优化，也可以接受第二次 `updated=0 skipped=7`，但绝对不应第二次再次插入相同行。

## 12. Schema guard 与异常处理

| 场景 | 处理方式 | 是否阻塞入库 | 是否记录 validation event |
|---|---|---|---|
| 缺少 `reportSpecification` | 阻断 | yes | yes |
| 缺少 `salesAndTrafficByDate` | 阻断第一版入库 | yes | yes |
| 缺少 `salesAndTrafficByAsin` | 默认 warning；不应让核心 date-level Sales & Traffic 全部停写；如 ASIN 表业务要求变化再单独收紧 | no | yes |
| `dateGranularity` 非 `DAY` | `requires_review=True` | yes | yes |
| 出现新增 JSON path | 记录 `new_fields` warning；继续按原 mapping 入库，未知字段保留在 raw data | no | yes |
| decimal/int 解析失败 | 阻断 execute | yes | yes |
| currencyCode 不一致 | warning 或 review；第一版建议 review | yes for first version | yes |
| JSON 解析失败 | 阻断 dry-run/execute | yes | yes if possible |

第一版 expected schema 曾覆盖当前 94 个 observed JSON path。2026-08-08 起，本功能按 `feature_schema_guard_resilience.md` / ADR-013 修订为“向后兼容数据契约”：`expected_fields` 仅用于已知字段目录和 drift 观测，`required_fields` 只保留安全入库所需的最小核心契约；**新增 JSON path 不再阻断**。

### 12.1 2026-08-08 schema guard robustness v1.1 实现

2026-08-03 真实自动化运行观察到 24 个新增 JSON path，`missing_fields=[]`，但旧策略仍返回 `requires_review=True` 并阻断写库。该行为已确认属于 false-positive blocking。v1.1 已按以下规则实现：

| 场景 | 新行为 | 是否阻塞 |
|---|---|---|
| 仅出现新增 JSON path | `status=new_fields`, warning, `requires_review=False` | no |
| 已知非关键字段缺失 | warning/info | no |
| required field 缺失 | `requires_review=True` | yes |
| `dateGranularity != DAY` | semantic incompatibility | yes |
| 核心 decimal/int/JSON 解析失败 | error | yes |

v1.1 required raw contract 已实现为：

```text
reportSpecification.reportType
reportSpecification.reportOptions.dateGranularity
salesAndTrafficByDate[].date
salesAndTrafficByDate[].salesByDate.orderedProductSales.amount
salesAndTrafficByDate[].salesByDate.unitsOrdered
salesAndTrafficByDate[].trafficByDate.sessions
```

ASIN section 的身份字段后续采用 row-level/conditional validation；不再把所有 observed path 全部视为 required。Amazon 新增的 shipped/refund/B2B/feedback 字段暂不新增 SQL column，继续由 raw file / `raw_data` 保留。

## 13. 审计与可追溯性

| 审计对象 | 表/字段 | 说明 |
|---|---|---|
| 任务运行 | `amazon_sync_run_log` | `job_name`, `workflow_name`, `status`, `rows_read`, `rows_written`, `rows_skipped`, `rows_failed`, `message`。 |
| Schema validation | `amazon_schema_validation_event` | `observed_fields_json`, `expected_fields_json`, `missing_fields_json`, `new_fields_json`, `requires_review`。 |
| 源文件路径 | normalized tables `source_raw_file_path` | 首版先保存路径，后续补 `source_raw_file_id` 外键。 |
| 源行 | `source_row_hash`, `raw_data` | 对 date row 和 asin row 分别生成。 |
| 本次运行 | `source_run_id` | 对应 `amazon_sync_run_log.id`。 |

## 14. 建议 CLI

建议新增专用入口：

```powershell
python scripts/ingest_sales_traffic_report.py --marketplace-id ATVPDKIKX0DER
python scripts/ingest_sales_traffic_report.py --marketplace-id ATVPDKIKX0DER --execute
```

可选参数：

```powershell
--raw-file <path>
--output-dir runtime/ingestion/sp_api/GET_SALES_AND_TRAFFIC_REPORT/...
```

说明：按照 `ADR-005-progressive-generalization.md`，当前仍采用专用入口，不急于做通用 `ingest_sp_api_reports.py`。

## 15. 相关代码路径

已新增：

| 路径 | 用途 |
|---|---|
| `scripts/ingest_sales_traffic_report.py` | Sales & Traffic 专用 CLI。 |
| `src/seller_data_pipeline/ingestion/sales_traffic_table_mapping.py` | 字段映射、expected schema、DB row 生成。 |
| `src/seller_data_pipeline/ingestion/sales_traffic_ingestion_dry_run.py` | dry-run preview 与 schema guard。 |
| `src/seller_data_pipeline/ingestion/sales_traffic_ingestion.py` | execute orchestration。 |
| `src/seller_data_pipeline/db/repositories/sales_repo.py` | Azure SQL MERGE/upsert repository，同时写两张表。 |
| `tests/unit/ingestion/test_sales_traffic_table_mapping.py` | 字段映射测试。 |
| `tests/unit/ingestion/test_sales_traffic_ingestion_dry_run.py` | dry-run 测试。 |
| `tests/unit/ingestion/test_sales_traffic_ingestion.py` | execute orchestration 测试。 |
| `tests/unit/db/test_sales_repo.py` | repository SQL/upsert 行为测试。 |

可复用：

- `src/seller_data_pipeline/common/exceptions.py`
- `src/seller_data_pipeline/common/hashing.py`（如已有）或现有 ingestion hash 工具
- `src/seller_data_pipeline/db/connection.py`
- `scripts/export_database_schema_spec.py`

## 16. 验收标准

### 16.1 设计与数据库验收

- 本文档完成并进入 `docs/features/README.md` 索引。
- `005_add_sales_traffic_business_key_hashes.sql` 已执行成功，5/5 batches。
- 已运行 `scripts/export_database_schema_spec.py --output-prefix after_005_sales_traffic_business_keys --include-row-counts`。
- `docs/database/database_current_schema_spec.md` 已据真实 schema 更新两张表的 `business_key_hash` 和唯一过滤索引。

### 16.2 代码验收

- `python scripts/ingest_sales_traffic_report.py --marketplace-id ATVPDKIKX0DER` dry-run 已成功。
- dry-run 输出合计 `prepared_rows=7`、`requires_review=False`；其中 daily 预期 6 行，asin 预期 1 行。
- `--execute` 首次写入成功：sync_run_id=7，daily inserted=6，asin inserted=1。
- 第二次 `--execute` 幂等性通过：sync_run_id=8，daily updated=6，asin updated=1。
- `amazon_sales_traffic_daily` 行数与 expected daily rows 一致：6。
- `amazon_sales_traffic_asin_daily` 行数与 expected asin rows 一致：1。
- `amazon_sync_run_log` 有成功记录。
- `amazon_schema_validation_event` 有 `validation_status=ok` 记录。
- `pytest` 已通过：145 passed。
- `compileall` 已通过。
- 本功能文档、progress 文档、数据库 spec 同步完成。

## 17. 当前限制与后续优化

1. 2026-08-03 已观察到 Amazon 在该 report 中新增 24 个字段；v1.1 已按 ADR-013 改为 non-blocking warning，并由单元测试覆盖完整 24-path 回归。
2. 当前样例 ASIN 维度疑似 Parent 粒度；后续需要确认 CHILD 粒度是否会出现 `childAsin`。
3. 第一版只支持 `dateGranularity=DAY`；WEEK/MONTH 应另行设计。
4. 当前不直接和订单、结算、广告、库存合并；这些进入后续分析功能。
5. 当前不写 `amazon_raw_report_file` 外键；后续应补充 raw registry。

## 18. 弃置记录

| 日期 | 方案 | 处理 | 原因 |
|---|---|---|---|
| 2026-05-17 | 直接做通用 `ingest_sp_api_reports.py` 同时支持 Listing / Inventory / Sales | 暂缓 | 按渐进式抽象规则，继续使用专用入口，等多条 SP-API ingestion 链路稳定后再抽象。 |


## 19. v1.1 Schema Guard 实现验证记录

| 日期 | 验证项 | 结果 |
|---|---|---|
| 2026-08-08 | 2026-08-03 24 个 additive JSON path 回归 | `status=new_fields`, `requires_review=False`, `prepared_rows=2` |
| 2026-08-08 | required `salesAndTrafficByDate[].date` 缺失 | `requires_review=True`, `prepared_rows=0` |
| 2026-08-08 | validation event | 仍记录 `new_fields_json`，non-blocking drift 的 `requires_review=False` |
| 2026-08-08 | 全量测试 | `313 passed`; `compileall` success |

Azure 生产/手动 Job 验收尚未执行；本地代码阶段完成后不得把该项写成已云端恢复。


### v1.83 Monthly period ingestion

默认/manual/weekly 未传日期窗口时仍使用 latest raw file。Monthly collect 显式传 `--start-date/--end-date`，CLI 通过 report request manifests 选择目标月全部 downloaded chunks；区间存在缺口时非零退出，不允许“只入最新 chunk”后继续生成月报。
