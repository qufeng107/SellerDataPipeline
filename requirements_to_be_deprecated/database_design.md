# SellerDataPipeline Amazon 数据与数据库设计文档

> Legacy migration source: 本文件是上一版整合设计文档，暂时保留作为迁移来源。新设计不应继续追加到本文件；后续会拆分到 `docs/data_access/` 和 `docs/features/`。如果与 `docs/` 下正式文档冲突，以 `docs/` 为准。

> 文档版本：v2.0  
> 更新日期：2026-05-16  
> 文档定位：**设计唯一事实**。本文件描述“应该如何设计”：Amazon 可获取哪些文件/API、文件结构、可提取字段、目标数据表、入库与维护规则。  
> 当前真实数据库结构不要在本文件维护；真实结构见 `requirements/database_current_schema_spec.md`。旧 `requirements/database_spec.md` 已改为兼容入口，不再维护详细设计。

---

## 1. 维护原则

1. 先更新本文档的设计，再改 parser / mapping / repository。
2. 对照 `database_current_schema_spec.md` 找出设计与真实库差异，再新增 SQL migration；已执行的 `001/002` 不再修改。
3. migration 执行成功后，更新 `database_current_schema_spec.md`，只记录真实结构，不夹杂未来设计。
4. 所有 Amazon raw file 必须先归档，再做 schema validation，再进入 normalized 表。
5. 字段漂移、新字段、缺字段、未映射字段默认阻断入库并记录 `amazon_schema_validation_event.requires_review=1`。

## 2. 数据源总览

| 来源 | 获取方式 | 常见文件结构 | raw 留存路径 | 当前状态 |
|---|---|---|---|---|
| SP-API Reports | createReport / getReports + getReportDocument | TSV/TXT flat file 或 JSON | `reports/raw/amazon/{marketplace_id}/{report_type}/{date}/...` | 多数核心报表已取样，首批表已建，normalized repository 待逐步补齐 |
| Amazon Ads API | Reporting v3 + Profiles API | JSON top-level array | `reports/raw/amazon_ads/{profile_id}/{report_type_id}/{date}/...` | 4 张 Sponsored Products 日表已真实入库并通过幂等测试 |
| 手工成本输入 | SQL seed / 后续 Excel/后台 | 手工维护表 | N/A | `amazon_sku_cost` 已建表，后续用于利润核算 |

## 3. 取样文件、结构、字段和目标表

| report / API | 文件结构 | 当前样例 | 可提取的核心字段/数据 | 目标表 | 当前实现状态 |
|---|---|---:|---|---|---|
| `spAdvertisedProduct` | Amazon Ads JSON top-level array | 32 | `[].adGroupId`, `[].adGroupName`, `[].advertisedAsin`, `[].advertisedSku`, `[].campaignId`, `[].campaignName`, `[].clicks`, `[].cost` ... | `amazon_ads_sp_advertised_product_daily` | 已真实入库；幂等测试通过 |
| `spCampaigns` | Amazon Ads JSON top-level array | 8 | `[].campaignId`, `[].campaignName`, `[].campaignStatus`, `[].clicks`, `[].cost`, `[].date`, `[].impressions`, `[].purchases7d` ... | `amazon_ads_sp_campaign_daily` | 已真实入库；幂等测试通过 |
| `spPurchasedProduct` | Amazon Ads JSON top-level array | 0 | `[]` | `amazon_ads_sp_purchased_product_daily` | API 可用但样例为空；暂不建表 |
| `spSearchTerm` | Amazon Ads JSON top-level array | 61 | `[].adGroupId`, `[].adGroupName`, `[].campaignId`, `[].campaignName`, `[].clicks`, `[].cost`, `[].date`, `[].impressions` ... | `amazon_ads_sp_search_term_daily` | 已真实入库；幂等测试通过 |
| `spTargeting` | Amazon Ads JSON top-level array | 99 | `[].adGroupId`, `[].adGroupName`, `[].campaignId`, `[].campaignName`, `[].clicks`, `[].cost`, `[].date`, `[].impressions` ... | `amazon_ads_sp_targeting_daily` | 已真实入库；幂等测试通过 |
| `GET_COUPON_PERFORMANCE_REPORT` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 2 | `coupons[].asins[].asin`, `coupons[].budget`, `coupons[].budgetPercentageUsed`, `coupons[].budgetRemaining`, `coupons[].budgetSpent`, `coupons[].clips`, `coupons[].couponId`, `coupons[].currencyCode` ... | `amazon_coupon_performance, amazon_coupon_asin` | 已取样；表已建；repository 待补 |
| `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 8 | `sku`, `fnsku`, `asin`, `amazon-store`, `product-name`, `product-group`, `brand`, `fulfilled-by` ... | `amazon_fba_fee_preview` | 已取样；表已建；repository 待补 |
| `GET_FBA_INVENTORY_PLANNING_DATA` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 4 | `snapshot-date`, `sku`, `fnsku`, `asin`, `product-name`, `condition`, `available`, `pending-removal-quantity` ... | `amazon_inventory_planning_daily` | 已取样；表已建；repository 待补 |
| `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 5 | `sku`, `fnsku`, `asin`, `product-name`, `condition`, `your-price`, `mfn-listing-exists`, `mfn-fulfillable-quantity` ... | `amazon_inventory_daily, amazon_listing_snapshot` | 已取样；表已建；parser 有单元测试；repository 待补 |
| `GET_FBA_REIMBURSEMENTS_DATA` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 19 | `approval-date`, `reimbursement-id`, `case-id`, `amazon-order-id`, `reason`, `sku`, `fnsku`, `asin` ... | `amazon_fba_reimbursement` | 已取样；表已建；repository 待补 |
| `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 112 | `amazon-order-id`, `merchant-order-id`, `purchase-date`, `last-updated-date`, `order-status`, `fulfillment-channel`, `sales-channel`, `order-channel` ... | `amazon_order_item` | 已取样；表已建；repository 待补 |
| `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 0 | `Order ID`, `Order date`, `Return request date`, `Return request status`, `Amazon RMA ID`, `Merchant RMA ID`, `Label type`, `Label cost` ... | `amazon_return_request` | 空样例；未建 return 表；后续非空样例后再设计 |
| `GET_LEDGER_DETAIL_VIEW_DATA` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 207 | `Date`, `FNSKU`, `ASIN`, `MSKU`, `Title`, `Event Type`, `Reference ID`, `Quantity` ... | `amazon_inventory_ledger_detail` | 已取样；表已建；目标表为 ledger detail；repository 待补 |
| `GET_LEDGER_SUMMARY_VIEW_DATA` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 150 | `Date`, `FNSKU`, `ASIN`, `MSKU`, `Title`, `Disposition`, `Starting Warehouse Balance`, `In Transit Between Warehouses` ... | `amazon_inventory_ledger_summary_daily` | 已取样；表已建；repository 待补 |
| `GET_MERCHANT_LISTINGS_ALL_DATA` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 6 | `item-name`, `item-description`, `listing-id`, `seller-sku`, `price`, `quantity`, `open-date`, `image-url` ... | `amazon_listing_snapshot, amazon_inventory_daily` | 已取样；表已建；parser 有单元测试；repository 待补 |
| `GET_PROMOTION_PERFORMANCE_REPORT` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 1 | `promotions[].createdDateTime`, `promotions[].endDateTime`, `promotions[].glanceViews`, `promotions[].includedProducts[].asin`, `promotions[].includedProducts[].productGlanceViews`, `promotions[].includedProducts[].productName`, `promotions[].includedProducts[].productRevenue`, `promotions[].includedProducts[].productRevenueCurrencyCode` ... | `amazon_promotion_performance, amazon_promotion_product_performance` | 已取样；表已建；repository 待补 |
| `GET_RESERVED_INVENTORY_DATA` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 5 | `sku`, `fnsku`, `asin`, `product-name`, `reserved_qty`, `reserved_customerorders`, `reserved_fc-transfers`, `reserved_fc-processing` ... | `amazon_reserved_inventory_daily` | 已取样；表已建；repository 待补 |
| `GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 5 | `Country`, `Product Name`, `FNSKU`, `Merchant SKU`, `ASIN`, `Condition`, `Supplier`, `Supplier part no.` ... | `amazon_inventory_planning_daily` | 已取样；暂并入 inventory planning 设计，字段待复核 |
| `GET_SALES_AND_TRAFFIC_REPORT` | JSON，包含 salesAndTrafficByDate / salesAndTrafficByAsin 数组 | 6 | `reportSpecification.dataEndTime`, `reportSpecification.dataStartTime`, `reportSpecification.marketplaceIds[]`, `reportSpecification.reportOptions.asinGranularity`, `reportSpecification.reportOptions.dateGranularity`, `reportSpecification.reportType`, `salesAndTrafficByAsin[].parentAsin`, `salesAndTrafficByAsin[].salesByAsin.orderedProductSales.amount` ... | `amazon_sales_traffic_daily, amazon_sales_traffic_asin_daily` | 已取样；表已建；parser 有单元测试；repository 待补 |
| `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | TSV/TXT flat file 或 report 专用 JSON，按样例确认 | 4911 | settlement-id, transaction-type, amount-type, amount-description, amount, sku/order 等结算明细 | `amazon_settlement_transaction, amazon_finance_event` | 已取样 8 份；表已建；分类规则已有；repository 待补 |

## 4. 目标表分层设计

| 层级 | 表 | 设计目的 |
|---|---|---|
| 基础维表 | `amazon_marketplace` | 市场、币种、SP-API endpoint。 数据来源：手工 seed / Amazon marketplace metadata。 |
| 审计控制 | `amazon_sync_run_log` | 任务运行状态、行数、耗时、错误信息。 数据来源：所有采集/解析/入库任务。 |
| 请求控制 | `amazon_report_request` | 报告请求、状态、document id、下载/解析状态。 数据来源：SP-API Reports createReport/getReports。 |
| raw 归档 | `amazon_raw_report_file` | 原始文件路径、hash、行列数、编码、下载时间。 数据来源：所有 Amazon SP-API / Ads raw files。 |
| 字段目录 | `amazon_report_field_catalog` | 观察到的源字段、目标表/字段建议、样例值。 数据来源：字段取样/分析脚本。 |
| schema 守门 | `amazon_schema_validation_event` | 字段漂移、缺字段、新字段、requires_review 和通知状态。 数据来源：下载后/入库前 schema validation。 |
| 成本配置 | `amazon_sku_cost` | SKU 采购、头程、包装等单位成本。 数据来源：手工维护/会计成本输入。 |
| Listing 快照 | `amazon_listing_snapshot` | SKU/ASIN/listing 状态、标题、价格、履约渠道。 数据来源：GET_MERCHANT_LISTINGS_ALL_DATA。 |
| 库存快照 | `amazon_inventory_daily` | FBA 可售、不可售、预留、入库、研究中等库存数量。 数据来源：GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA。 |
| 销售流量-日期 | `amazon_sales_traffic_daily` | 日期维度销售额、订单、退款、sessions、page views、转化率。 数据来源：GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByDate。 |
| 销售流量-ASIN | `amazon_sales_traffic_asin_daily` | ASIN 维度销售、流量、转化率。 数据来源：GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByAsin。 |
| 结算明细 | `amazon_settlement_transaction` | 实际入账财务明细、费用、退款、广告扣费、Coupon/Deal 费用、分类字段。 数据来源：GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2。 |
| 订单明细 | `amazon_order_item` | 订单/SKU 行、金额、税、促销、发货地区。 数据来源：GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL。 |
| FBA 赔偿 | `amazon_fba_reimbursement` | 赔偿原因、case、SKU、金额、现金/库存赔偿数量。 数据来源：GET_FBA_REIMBURSEMENTS_DATA。 |
| FBA 费用预估 | `amazon_fba_fee_preview` | SKU 尺寸、重量、预估 referral/FBA fulfillment fee。 数据来源：GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA。 |
| 库存流水汇总 | `amazon_inventory_ledger_summary_daily` | 每日/地点维度仓库库存变动汇总。 数据来源：GET_LEDGER_SUMMARY_VIEW_DATA。 |
| 库存流水明细 | `amazon_inventory_ledger_detail` | FBA 仓库事件明细、reference、数量、原因。 数据来源：GET_LEDGER_DETAIL_VIEW_DATA。 |
| 预留库存 | `amazon_reserved_inventory_daily` | 预留数量按 customer orders / FC transfer / processing 拆分。 数据来源：GET_RESERVED_INVENTORY_DATA。 |
| 库存健康/补货 | `amazon_inventory_planning_daily` | 库龄、售罄率、days of supply、推荐动作。 数据来源：GET_FBA_INVENTORY_PLANNING_DATA / GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT。 |
| 促销主表 | `amazon_promotion_performance` | 活动总体浏览、销量、销售额、状态与时间。 数据来源：GET_PROMOTION_PERFORMANCE_REPORT。 |
| 促销商品明细 | `amazon_promotion_product_performance` | 活动 ASIN 维度表现。 数据来源：GET_PROMOTION_PERFORMANCE_REPORT.productPerformance。 |
| Coupon 主表 | `amazon_coupon_performance` | Coupon 预算、领取、兑换、折扣、销售额。 数据来源：GET_COUPON_PERFORMANCE_REPORT。 |
| Coupon ASIN | `amazon_coupon_asin` | Coupon 关联 ASIN。 数据来源：GET_COUPON_PERFORMANCE_REPORT.asins。 |
| Ads profile | `amazon_ads_profile` | profile、国家、币种、账户类型、支付状态。 数据来源：Amazon Ads Profiles API。 |
| 广告 campaign 日表 | `amazon_ads_sp_campaign_daily` | SP campaign 日维度曝光、点击、花费、7日销售/购买。 数据来源：Amazon Ads spCampaigns。 |
| 广告 targeting 日表 | `amazon_ads_sp_targeting_daily` | 关键词/target 日维度表现。 数据来源：Amazon Ads spTargeting。 |
| 广告 search term 日表 | `amazon_ads_sp_search_term_daily` | 用户搜索词表现，用于加词/否词。 数据来源：Amazon Ads spSearchTerm。 |
| 广告 advertised product 日表 | `amazon_ads_sp_advertised_product_daily` | 广告 SKU/ASIN 日维度表现。 数据来源：Amazon Ads spAdvertisedProduct。 |

## 5. 核心业务键与 upsert 规则

| 表 | 业务唯一键 / 当前策略 | 说明 |
|---|---|---|
| `amazon_ads_sp_campaign_daily` | profile_id + report_date + campaign_id -> business_key_hash | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |
| `amazon_ads_sp_targeting_daily` | profile_id + report_date + campaign_id + ad_group_id + keyword_id + targeting + match_type -> business_key_hash | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |
| `amazon_ads_sp_search_term_daily` | profile_id + report_date + campaign_id + ad_group_id + keyword_id + targeting + search_term + match_type -> business_key_hash | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |
| `amazon_ads_sp_advertised_product_daily` | profile_id + report_date + campaign_id + ad_group_id + advertised_asin + advertised_sku -> business_key_hash | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |
| `amazon_listing_snapshot` | marketplace_id + snapshot_date + seller_sku + listing_id；当前仅索引，repository 未补 | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |
| `amazon_inventory_daily` | marketplace_id + snapshot_date + seller_sku + fnsku + asin；当前仅索引，repository 未补 | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |
| `amazon_sales_traffic_daily` | marketplace_id + report_date；当前仅索引，repository 未补 | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |
| `amazon_sales_traffic_asin_daily` | marketplace_id + report_start_date + report_end_date + parent_asin + child_asin；当前仅索引，repository 未补 | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |
| `amazon_settlement_transaction` | 第一阶段以 source_report_id + source_row_hash 追溯；分类后可补业务键策略 | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |
| `amazon_order_item` | marketplace_id + amazon_order_id + seller_sku + asin；当前仅索引，repository 未补 | `source_row_hash` 只做 raw 追溯；能稳定定义业务键时优先业务键。 |

## 6. 入库守门和审计设计

```text
raw file 下载/发现
  -> amazon_raw_report_file 归档（当前 Ads 首轮尚未完整关联 raw_file_id，后续补）
  -> schema validation
  -> parser normalized rows
  -> dry-run preview
  -> repository upsert
  -> amazon_sync_run_log / amazon_schema_validation_event
```

可直接入库状态：`ok`。  
可接受但不写业务表：`empty_report`。  
必须人工检查并阻断：`new_fields`、`missing_fields`、`schema_drift`、`unmapped_fields`、`validation_failed`、`no_expected_schema`、`parser_failed`、`upsert_failed`。

## 7. 下一批开发顺序

1. 保留 Ads 链路为第一条已跑通模板。
2. 先补 `amazon_listing_snapshot` repository/upsert。
3. 再补 `amazon_inventory_daily`。
4. 再补 `amazon_sales_traffic_daily` / `amazon_sales_traffic_asin_daily`。
5. 再补 `amazon_settlement_transaction`，同时固化利润分类规则。
6. 最后接 Azure Container Apps Jobs 与邮件通知。
