# SellerDataPipeline 当前真实数据库 Schema Spec

> 文档版本：v1.2  
> 更新日期：2026-05-16  
> 文档定位：**当前真实实现记录**。本文件只记录已经在 Azure SQL `amazon_ops` 执行成功的表、字段、索引与数据来源；不写未来设计。设计变更请先更新对应的 `docs/features/feature_*.md` 或 `docs/data_access/*.md`；如涉及库结构变化，先对比本文件，再新增 migration；migration 执行成功后再更新本文件。

## 1. 当前数据库状态

| 项目 | 当前值 |
|---|---|
| Azure SQL database | `amazon_ops` |
| Server | `amazon-ops-sql` |
| 已执行 migration | `001_create_core_tables.sql` 29/29 batches；`002_create_indexes.sql` 54/54 batches；`003_add_listing_snapshot_business_key_hash.sql` 3/3 batches |
| 用户表数量 | 28 |
| 已真实入库验证 | Amazon Ads 4 张 SP 日表，首次 inserted=200、重复执行 inserted=0/updated=200；Listing 快照表首次 inserted=6、重复执行 inserted=0/updated=6 |
| 当前限制 | `amazon_sync_run_log` 尚无 rows_inserted / rows_updated 字段；Ads/Listing 首轮 `raw_file_id` 尚为 NULL；Inventory/Sales/Settlement 等 SP-API normalized repository 尚未实现 |

## 2. 表清单与数据来源

| 表 | 类型 | 数据来源 | 说明 |
|---|---|---|---|
| `amazon_marketplace` | 基础维表 | 手工 seed / Amazon marketplace metadata | 市场、币种、SP-API endpoint。 |
| `amazon_sync_run_log` | 审计控制 | 所有采集/解析/入库任务 | 任务运行状态、行数、耗时、错误信息。 |
| `amazon_report_request` | 请求控制 | SP-API Reports createReport/getReports | 报告请求、状态、document id、下载/解析状态。 |
| `amazon_raw_report_file` | raw 归档 | 所有 Amazon SP-API / Ads raw files | 原始文件路径、hash、行列数、编码、下载时间。 |
| `amazon_report_field_catalog` | 字段目录 | 字段取样/分析脚本 | 观察到的源字段、目标表/字段建议、样例值。 |
| `amazon_schema_validation_event` | schema 守门 | 下载后/入库前 schema validation | 字段漂移、缺字段、新字段、requires_review 和通知状态。 |
| `amazon_sku_cost` | 成本配置 | 手工维护/会计成本输入 | SKU 采购、头程、包装等单位成本。 |
| `amazon_listing_snapshot` | Listing 快照 | GET_MERCHANT_LISTINGS_ALL_DATA | SKU/ASIN/listing 状态、标题、价格、履约渠道。 |
| `amazon_inventory_daily` | 库存快照 | GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA | FBA 可售、不可售、预留、入库、研究中等库存数量。 |
| `amazon_sales_traffic_daily` | 销售流量-日期 | GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByDate | 日期维度销售额、订单、退款、sessions、page views、转化率。 |
| `amazon_sales_traffic_asin_daily` | 销售流量-ASIN | GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByAsin | ASIN 维度销售、流量、转化率。 |
| `amazon_settlement_transaction` | 结算明细 | GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2 | 实际入账财务明细、费用、退款、广告扣费、Coupon/Deal 费用、分类字段。 |
| `amazon_order_item` | 订单明细 | GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL | 订单/SKU 行、金额、税、促销、发货地区。 |
| `amazon_fba_reimbursement` | FBA 赔偿 | GET_FBA_REIMBURSEMENTS_DATA | 赔偿原因、case、SKU、金额、现金/库存赔偿数量。 |
| `amazon_fba_fee_preview` | FBA 费用预估 | GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA | SKU 尺寸、重量、预估 referral/FBA fulfillment fee。 |
| `amazon_inventory_ledger_summary_daily` | 库存流水汇总 | GET_LEDGER_SUMMARY_VIEW_DATA | 每日/地点维度仓库库存变动汇总。 |
| `amazon_inventory_ledger_detail` | 库存流水明细 | GET_LEDGER_DETAIL_VIEW_DATA | FBA 仓库事件明细、reference、数量、原因。 |
| `amazon_reserved_inventory_daily` | 预留库存 | GET_RESERVED_INVENTORY_DATA | 预留数量按 customer orders / FC transfer / processing 拆分。 |
| `amazon_inventory_planning_daily` | 库存健康/补货 | GET_FBA_INVENTORY_PLANNING_DATA / GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT | 库龄、售罄率、days of supply、推荐动作。 |
| `amazon_promotion_performance` | 促销主表 | GET_PROMOTION_PERFORMANCE_REPORT | 活动总体浏览、销量、销售额、状态与时间。 |
| `amazon_promotion_product_performance` | 促销商品明细 | GET_PROMOTION_PERFORMANCE_REPORT.productPerformance | 活动 ASIN 维度表现。 |
| `amazon_coupon_performance` | Coupon 主表 | GET_COUPON_PERFORMANCE_REPORT | Coupon 预算、领取、兑换、折扣、销售额。 |
| `amazon_coupon_asin` | Coupon ASIN | GET_COUPON_PERFORMANCE_REPORT.asins | Coupon 关联 ASIN。 |
| `amazon_ads_profile` | Ads profile | Amazon Ads Profiles API | profile、国家、币种、账户类型、支付状态。 |
| `amazon_ads_sp_campaign_daily` | 广告 campaign 日表 | Amazon Ads spCampaigns | SP campaign 日维度曝光、点击、花费、7日销售/购买。 |
| `amazon_ads_sp_targeting_daily` | 广告 targeting 日表 | Amazon Ads spTargeting | 关键词/target 日维度表现。 |
| `amazon_ads_sp_search_term_daily` | 广告 search term 日表 | Amazon Ads spSearchTerm | 用户搜索词表现，用于加词/否词。 |
| `amazon_ads_sp_advertised_product_daily` | 广告 advertised product 日表 | Amazon Ads spAdvertisedProduct | 广告 SKU/ASIN 日维度表现。 |

## 3. 索引清单

| 表 | 索引 | 唯一 | 字段 | 过滤条件 |
|---|---|---|---|---|
| `amazon_marketplace` | `UX_amazon_marketplace_marketplace_id` | 是 | `marketplace_id` |  |
| `amazon_sync_run_log` | `IX_amazon_sync_run_log_job_started` | 否 | `job_name, started_at DESC` |  |
| `amazon_sync_run_log` | `IX_amazon_sync_run_log_status_started` | 否 | `status, started_at DESC` |  |
| `amazon_sync_run_log` | `IX_amazon_sync_run_log_workflow_started` | 否 | `workflow_name, started_at DESC` |  |
| `amazon_report_request` | `UX_amazon_report_request_report_id` | 是 | `marketplace_id, source_system, report_type, report_id` | `report_id IS NOT NULL` |
| `amazon_report_request` | `IX_amazon_report_request_status` | 否 | `processing_status, download_status, parse_status, requested_at DESC` |  |
| `amazon_report_request` | `IX_amazon_report_request_type_range` | 否 | `source_system, report_type, marketplace_id, data_start_time, data_end_time` |  |
| `amazon_raw_report_file` | `UX_amazon_raw_report_file_path` | 是 | `storage_backend, file_path` |  |
| `amazon_raw_report_file` | `IX_amazon_raw_report_file_report` | 否 | `source_system, report_type, marketplace_id, downloaded_at DESC` |  |
| `amazon_raw_report_file` | `IX_amazon_raw_report_file_sha256` | 否 | `sha256` |  |
| `amazon_report_field_catalog` | `IX_amazon_report_field_catalog_report` | 否 | `source_system, report_type, marketplace_id, field_position` |  |
| `amazon_schema_validation_event` | `IX_amazon_schema_validation_event_report` | 否 | `source_system, report_type, marketplace_id, created_at DESC` |  |
| `amazon_schema_validation_event` | `IX_amazon_schema_validation_event_review` | 否 | `requires_review, notification_status, created_at DESC` |  |
| `amazon_sku_cost` | `IX_amazon_sku_cost_effective` | 否 | `marketplace_id, seller_sku, effective_from, effective_to` |  |
| `amazon_listing_snapshot` | `IX_amazon_listing_snapshot_key` | 否 | `marketplace_id, snapshot_date DESC, seller_sku, listing_id` |  |
| `amazon_listing_snapshot` | `IX_amazon_listing_snapshot_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_listing_snapshot` | `UX_amazon_listing_snapshot_business_key_hash` | 是 | `business_key_hash` | `business_key_hash IS NOT NULL` |
| `amazon_inventory_daily` | `IX_amazon_inventory_daily_key` | 否 | `marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin` |  |
| `amazon_inventory_daily` | `IX_amazon_inventory_daily_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_sales_traffic_daily` | `IX_amazon_sales_traffic_daily_date` | 否 | `marketplace_id, report_date DESC` |  |
| `amazon_sales_traffic_daily` | `IX_amazon_sales_traffic_daily_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_sales_traffic_asin_daily` | `IX_amazon_sales_traffic_asin_daily_key` | 否 | `marketplace_id, report_start_date DESC, report_end_date DESC, parent_asin, child_asin` |  |
| `amazon_sales_traffic_asin_daily` | `IX_amazon_sales_traffic_asin_daily_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_settlement_transaction` | `IX_amazon_settlement_transaction_settlement` | 否 | `marketplace_id, settlement_id, is_settlement_summary, transaction_type` |  |
| `amazon_settlement_transaction` | `IX_amazon_settlement_transaction_order_sku` | 否 | `marketplace_id, order_id, seller_sku, amount_category, profit_bucket` |  |
| `amazon_settlement_transaction` | `IX_amazon_settlement_transaction_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_order_item` | `IX_amazon_order_item_order_sku` | 否 | `marketplace_id, amazon_order_id, seller_sku, asin` |  |
| `amazon_order_item` | `IX_amazon_order_item_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_fba_reimbursement` | `IX_amazon_fba_reimbursement_key` | 否 | `marketplace_id, reimbursement_id, case_id, seller_sku, asin` |  |
| `amazon_fba_reimbursement` | `IX_amazon_fba_reimbursement_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_fba_fee_preview` | `IX_amazon_fba_fee_preview_sku` | 否 | `marketplace_id, seller_sku, fnsku, asin` |  |
| `amazon_fba_fee_preview` | `IX_amazon_fba_fee_preview_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_inventory_ledger_summary_daily` | `IX_amazon_inventory_ledger_summary_daily_key` | 否 | `marketplace_id, seller_sku, fnsku, asin, ledger_date_raw` |  |
| `amazon_inventory_ledger_detail` | `IX_amazon_inventory_ledger_detail_key` | 否 | `marketplace_id, seller_sku, fnsku, asin, event_type, reference_id` |  |
| `amazon_reserved_inventory_daily` | `IX_amazon_reserved_inventory_daily_key` | 否 | `marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin` |  |
| `amazon_inventory_planning_daily` | `IX_amazon_inventory_planning_daily_key` | 否 | `marketplace_id, seller_sku, fnsku, asin, snapshot_date_raw` |  |
| `amazon_promotion_performance` | `IX_amazon_promotion_performance_key` | 否 | `marketplace_id, promotion_id, status` |  |
| `amazon_promotion_product_performance` | `IX_amazon_promotion_product_performance_key` | 否 | `marketplace_id, promotion_id, asin` |  |
| `amazon_coupon_performance` | `IX_amazon_coupon_performance_key` | 否 | `marketplace_id, coupon_id, merchant_id` |  |
| `amazon_coupon_asin` | `IX_amazon_coupon_asin_key` | 否 | `marketplace_id, coupon_id, asin` |  |
| `amazon_ads_profile` | `UX_amazon_ads_profile_profile_id` | 是 | `profile_id` |  |
| `amazon_ads_profile` | `IX_amazon_ads_profile_marketplace` | 否 | `marketplace_id, country_code, account_type` |  |
| `amazon_ads_sp_campaign_daily` | `IX_amazon_ads_sp_campaign_daily_key` | 否 | `profile_id, report_date DESC, campaign_id` |  |
| `amazon_ads_sp_campaign_daily` | `UX_amazon_ads_sp_campaign_daily_business_key` | 是 | `business_key_hash` |  |
| `amazon_ads_sp_campaign_daily` | `IX_amazon_ads_sp_campaign_daily_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_ads_sp_targeting_daily` | `IX_amazon_ads_sp_targeting_daily_key` | 否 | `profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id` |  |
| `amazon_ads_sp_targeting_daily` | `UX_amazon_ads_sp_targeting_daily_business_key` | 是 | `business_key_hash` |  |
| `amazon_ads_sp_targeting_daily` | `IX_amazon_ads_sp_targeting_daily_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_ads_sp_search_term_daily` | `IX_amazon_ads_sp_search_term_daily_key` | 否 | `profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id` |  |
| `amazon_ads_sp_search_term_daily` | `UX_amazon_ads_sp_search_term_daily_business_key` | 是 | `business_key_hash` |  |
| `amazon_ads_sp_search_term_daily` | `IX_amazon_ads_sp_search_term_daily_source` | 否 | `source_report_id, source_row_hash` |  |
| `amazon_ads_sp_advertised_product_daily` | `IX_amazon_ads_sp_advertised_product_daily_key` | 否 | `profile_id, report_date DESC, advertised_asin, advertised_sku` |  |
| `amazon_ads_sp_advertised_product_daily` | `UX_amazon_ads_sp_advertised_product_daily_business_key` | 是 | `business_key_hash` |  |
| `amazon_ads_sp_advertised_product_daily` | `IX_amazon_ads_sp_advertised_product_daily_campaign` | 否 | `profile_id, campaign_id, ad_group_id, report_date DESC` |  |
| `amazon_ads_sp_advertised_product_daily` | `IX_amazon_ads_sp_advertised_product_daily_source` | 否 | `source_report_id, source_row_hash` |  |

## 4. 字段结构

### 4.1 `amazon_marketplace`

- 数据来源：手工 seed / Amazon marketplace metadata
- 表用途：市场、币种、SP-API endpoint。
- 当前索引：`UX_amazon_marketplace_marketplace_id`(marketplace_id)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `marketplace_name` | `NVARCHAR(200)` | NOT NULL |  | 名称/标题字段。 |
| `country_code` | `NVARCHAR(10)` | NOT NULL |  | 国家代码。 |
| `currency` | `NVARCHAR(10)` | NOT NULL |  | 币种。 |
| `region` | `NVARCHAR(20)` | NOT NULL |  | Amazon SP-API 区域。 |
| `endpoint` | `NVARCHAR(300)` | NOT NULL |  | SP-API endpoint。 |
| `is_active` | `BIT` | NOT NULL | `1` | 是否启用该 marketplace。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.2 `amazon_sync_run_log`

- 数据来源：所有采集/解析/入库任务
- 表用途：任务运行状态、行数、耗时、错误信息。
- 当前索引：`IX_amazon_sync_run_log_job_started`(job_name, started_at DESC)；`IX_amazon_sync_run_log_status_started`(status, started_at DESC)；`IX_amazon_sync_run_log_workflow_started`(workflow_name, started_at DESC)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `workflow_name` | `NVARCHAR(120)` | NULL |  | 流程名称。 |
| `job_name` | `NVARCHAR(120)` | NOT NULL |  | 任务入口名称。 |
| `task_type` | `NVARCHAR(80)` | NULL |  | 任务类型，如 ingestion_upsert。 |
| `trigger_type` | `NVARCHAR(50)` | NOT NULL | `'manual'` | 触发方式，如 manual/scheduled。 |
| `run_mode` | `NVARCHAR(50)` | NOT NULL | `'local'` | 运行模式，如 local/azure_sql_write。 |
| `parent_run_id` | `BIGINT` | NULL |  | 源系统或本系统标识字段。 |
| `job_execution_id` | `NVARCHAR(200)` | NULL |  | 源系统或本系统标识字段。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `source_system` | `NVARCHAR(50)` | NULL |  | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `status` | `NVARCHAR(50)` | NOT NULL | `'running'` | 状态字段。 |
| `started_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 任务开始时间 UTC。 |
| `finished_at` | `DATETIME2` | NULL |  | 任务结束时间 UTC。 |
| `duration_ms` | `BIGINT` | NULL |  | 任务耗时毫秒。 |
| `date_start` | `DATE` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `date_end` | `DATE` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `rows_read` | `INT` | NOT NULL | `0` | 任务读取/解析的行数。 |
| `rows_written` | `INT` | NOT NULL | `0` | 任务写入或更新的行数。 |
| `rows_skipped` | `INT` | NOT NULL | `0` | 任务跳过的行数。 |
| `rows_failed` | `INT` | NOT NULL | `0` | 任务失败行数。 |
| `files_created` | `INT` | NOT NULL | `0` | 本次任务生成文件数量。 |
| `retry_count` | `INT` | NOT NULL | `0` | 重试次数。 |
| `config_snapshot_json` | `NVARCHAR(MAX)` | NULL |  | 任务配置快照 JSON。 |
| `message` | `NVARCHAR(MAX)` | NULL |  | 任务或验证事件说明。 |
| `error_type` | `NVARCHAR(200)` | NULL |  | 异常类型。 |
| `error_detail` | `NVARCHAR(MAX)` | NULL |  | 异常详情。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |

### 4.3 `amazon_report_request`

- 数据来源：SP-API Reports createReport/getReports
- 表用途：报告请求、状态、document id、下载/解析状态。
- 当前索引：`UX_amazon_report_request_report_id`(marketplace_id, source_system, report_type, report_id)；`IX_amazon_report_request_status`(processing_status, download_status, parse_status, requested_at DESC)；`IX_amazon_report_request_type_range`(source_system, report_type, marketplace_id, data_start_time, data_end_time)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL |  | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `report_type` | `NVARCHAR(120)` | NOT NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `report_options_json` | `NVARCHAR(MAX)` | NULL |  | JSON 结构化内容。 |
| `data_start_time` | `DATETIME2` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `data_end_time` | `DATETIME2` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `report_id` | `NVARCHAR(120)` | NULL |  | 源系统或本系统标识字段。 |
| `report_document_id` | `NVARCHAR(120)` | NULL |  | 源系统或本系统标识字段。 |
| `processing_status` | `NVARCHAR(50)` | NOT NULL | `'SUBMITTED'` | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `download_status` | `NVARCHAR(50)` | NOT NULL | `'PENDING'` | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `parse_status` | `NVARCHAR(50)` | NOT NULL | `'PENDING'` | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `requested_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 时间字段。 |
| `last_checked_at` | `DATETIME2` | NULL |  | 时间字段。 |
| `completed_at` | `DATETIME2` | NULL |  | 时间字段。 |
| `downloaded_at` | `DATETIME2` | NULL |  | 时间字段。 |
| `parsed_at` | `DATETIME2` | NULL |  | 时间字段。 |
| `retry_count` | `INT` | NOT NULL | `0` | 重试次数。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `error_message` | `NVARCHAR(MAX)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.4 `amazon_raw_report_file`

- 数据来源：所有 Amazon SP-API / Ads raw files
- 表用途：原始文件路径、hash、行列数、编码、下载时间。
- 当前索引：`UX_amazon_raw_report_file_path`(storage_backend, file_path)；`IX_amazon_raw_report_file_report`(source_system, report_type, marketplace_id, downloaded_at DESC)；`IX_amazon_raw_report_file_sha256`(sha256)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `report_request_id` | `BIGINT` | NULL |  | 源系统或本系统标识字段。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL |  | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `report_type` | `NVARCHAR(120)` | NOT NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `report_id` | `NVARCHAR(120)` | NULL |  | 源系统或本系统标识字段。 |
| `report_document_id` | `NVARCHAR(120)` | NULL |  | 源系统或本系统标识字段。 |
| `file_role` | `NVARCHAR(50)` | NOT NULL | `'raw'` | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `storage_backend` | `NVARCHAR(50)` | NOT NULL | `'local'` | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `file_path` | `NVARCHAR(700)` | NOT NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `file_name` | `NVARCHAR(300)` | NOT NULL |  | 名称/标题字段。 |
| `file_extension` | `NVARCHAR(30)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `content_type` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `compression_algorithm` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `encoding` | `NVARCHAR(80)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `delimiter` | `NVARCHAR(20)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `row_count` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `column_count` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sha256` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `byte_size` | `BIGINT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `downloaded_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 时间字段。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.5 `amazon_report_field_catalog`

- 数据来源：字段取样/分析脚本
- 表用途：观察到的源字段、目标表/字段建议、样例值。
- 当前索引：`IX_amazon_report_field_catalog_report`(source_system, report_type, marketplace_id, field_position)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL |  | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `report_type` | `NVARCHAR(120)` | NOT NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `sample_file_id` | `BIGINT` | NULL |  | 源系统或本系统标识字段。 |
| `field_position` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_field_name` | `NVARCHAR(300)` | NOT NULL |  | 名称/标题字段。 |
| `normalized_field_name` | `NVARCHAR(200)` | NULL |  | 名称/标题字段。 |
| `target_table` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `target_column` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `data_type_suggestion` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `nullable_observed` | `BIT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sample_values_json` | `NVARCHAR(MAX)` | NULL |  | JSON 结构化内容。 |
| `field_status` | `NVARCHAR(50)` | NOT NULL | `'observed'` | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `notes` | `NVARCHAR(MAX)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.6 `amazon_schema_validation_event`

- 数据来源：下载后/入库前 schema validation
- 表用途：字段漂移、缺字段、新字段、requires_review 和通知状态。
- 当前索引：`IX_amazon_schema_validation_event_report`(source_system, report_type, marketplace_id, created_at DESC)；`IX_amazon_schema_validation_event_review`(requires_review, notification_status, created_at DESC)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL |  | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_type` | `NVARCHAR(120)` | NOT NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `report_id` | `NVARCHAR(120)` | NULL |  | 源系统或本系统标识字段。 |
| `raw_file_id` | `BIGINT` | NULL |  | 源系统或本系统标识字段。 |
| `raw_file_path` | `NVARCHAR(1000)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `validation_stage` | `NVARCHAR(80)` | NOT NULL | `'post_download'` | 验证阶段。 |
| `validation_status` | `NVARCHAR(80)` | NOT NULL |  | schema validation 结果。 |
| `severity` | `NVARCHAR(50)` | NOT NULL | `'info'` | 事件级别。 |
| `row_count` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `observed_fields_json` | `NVARCHAR(MAX)` | NULL |  | 实际观察到的字段列表 JSON。 |
| `expected_fields_json` | `NVARCHAR(MAX)` | NULL |  | 期望字段列表 JSON。 |
| `missing_fields_json` | `NVARCHAR(MAX)` | NULL |  | 缺失字段 JSON。 |
| `new_fields_json` | `NVARCHAR(MAX)` | NULL |  | 新增字段 JSON。 |
| `unmapped_fields_json` | `NVARCHAR(MAX)` | NULL |  | 未映射字段 JSON。 |
| `requires_review` | `BIT` | NOT NULL | `0` | 是否需要人工检查。 |
| `notification_status` | `NVARCHAR(50)` | NOT NULL | `'not_required'` | 通知状态。 |
| `notified_at` | `DATETIME2` | NULL |  | 时间字段。 |
| `message` | `NVARCHAR(MAX)` | NULL |  | 任务或验证事件说明。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |

### 4.7 `amazon_sku_cost`

- 数据来源：手工维护/会计成本输入
- 表用途：SKU 采购、头程、包装等单位成本。
- 当前索引：`IX_amazon_sku_cost_effective`(marketplace_id, seller_sku, effective_from, effective_to)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `seller_sku` | `NVARCHAR(200)` | NOT NULL |  | 卖家 SKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `product_cost` | `DECIMAL(18,4)` | NOT NULL | `0` | 手工维护的产品采购成本。 |
| `first_mile_cost` | `DECIMAL(18,4)` | NOT NULL | `0` | 手工维护的头程单位成本。 |
| `packaging_cost` | `DECIMAL(18,4)` | NOT NULL | `0` | 手工维护的包装单位成本。 |
| `other_unit_cost` | `DECIMAL(18,4)` | NOT NULL | `0` | 其他单位成本。 |
| `currency` | `NVARCHAR(10)` | NOT NULL |  | 币种。 |
| `effective_from` | `DATE` | NOT NULL |  | 成本生效日期。 |
| `effective_to` | `DATE` | NULL |  | 成本失效日期。 |
| `remark` | `NVARCHAR(MAX)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.8 `amazon_listing_snapshot`

- 数据来源：GET_MERCHANT_LISTINGS_ALL_DATA
- 表用途：SKU/ASIN/listing 状态、标题、价格、履约渠道。
- 当前索引：`IX_amazon_listing_snapshot_key`(marketplace_id, snapshot_date DESC, seller_sku, listing_id)；`IX_amazon_listing_snapshot_source`(source_report_id, source_row_hash)；`UX_amazon_listing_snapshot_business_key_hash`(business_key_hash, filtered unique: business_key_hash IS NOT NULL)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `snapshot_date` | `DATE` | NOT NULL |  | 库存/Listing 快照日期。 |
| `listing_id` | `NVARCHAR(200)` | NOT NULL |  | 源系统或本系统标识字段。 |
| `seller_sku` | `NVARCHAR(200)` | NOT NULL |  | 卖家 SKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `product_id` | `NVARCHAR(100)` | NULL |  | 源系统或本系统标识字段。 |
| `product_id_type` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `item_name` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `item_description` | `NVARCHAR(MAX)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `price` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `currency` | `NVARCHAR(10)` | NULL |  | 币种。 |
| `quantity` | `INT` | NULL |  | 数量字段。 |
| `pending_quantity` | `INT` | NULL |  | 数量字段。 |
| `open_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `open_date_utc` | `DATETIME2` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `item_is_marketplace` | `BIT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `item_condition` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `fulfillment_channel` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `merchant_shipping_group` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `status` | `NVARCHAR(50)` | NULL |  | 状态字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.9 `amazon_inventory_daily`

- 数据来源：GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA
- 表用途：FBA 可售、不可售、预留、入库、研究中等库存数量。
- 当前索引：`IX_amazon_inventory_daily_key`(marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin)；`IX_amazon_inventory_daily_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `snapshot_date` | `DATE` | NOT NULL |  | 库存/Listing 快照日期。 |
| `seller_sku` | `NVARCHAR(200)` | NOT NULL |  | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL |  | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `condition` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `your_price` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `currency` | `NVARCHAR(10)` | NULL |  | 币种。 |
| `mfn_listing_exists` | `BIT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mfn_fulfillable_quantity` | `INT` | NULL |  | 数量字段。 |
| `afn_listing_exists` | `BIT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `afn_warehouse_quantity` | `INT` | NULL |  | 数量字段。 |
| `afn_fulfillable_quantity` | `INT` | NULL |  | 数量字段。 |
| `afn_unsellable_quantity` | `INT` | NULL |  | 数量字段。 |
| `afn_reserved_quantity` | `INT` | NULL |  | 数量字段。 |
| `afn_total_quantity` | `INT` | NULL |  | 数量字段。 |
| `per_unit_volume` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `afn_inbound_working_quantity` | `INT` | NULL |  | 数量字段。 |
| `afn_inbound_shipped_quantity` | `INT` | NULL |  | 数量字段。 |
| `afn_inbound_receiving_quantity` | `INT` | NULL |  | 数量字段。 |
| `afn_researching_quantity` | `INT` | NULL |  | 数量字段。 |
| `afn_reserved_future_supply` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `afn_future_supply_buyable` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `store` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.10 `amazon_sales_traffic_daily`

- 数据来源：GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByDate
- 表用途：日期维度销售额、订单、退款、sessions、page views、转化率。
- 当前索引：`IX_amazon_sales_traffic_daily_date`(marketplace_id, report_date DESC)；`IX_amazon_sales_traffic_daily_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL |  | 报表日期。 |
| `date_granularity` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `asin_granularity` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `ordered_product_sales_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `ordered_product_sales_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `ordered_product_sales_b2b_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `ordered_product_sales_b2b_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `average_sales_per_order_item_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `average_sales_per_order_item_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `average_sales_per_order_item_b2b_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `average_sales_per_order_item_b2b_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `average_units_per_order_item` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `average_units_per_order_item_b2b` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `average_selling_price_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `average_selling_price_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `average_selling_price_b2b_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `average_selling_price_b2b_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `units_ordered` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `units_ordered_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `total_order_items` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `total_order_items_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `units_refunded` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `refund_rate` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `claims_granted` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `claims_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `claims_amount_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `shipped_product_sales_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `shipped_product_sales_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `units_shipped` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `orders_shipped` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_page_views` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_page_views` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `page_views` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_sessions` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_sessions` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sessions` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `buy_box_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `order_item_session_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `unit_session_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `average_offer_count` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `average_parent_items` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `feedback_received` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `negative_feedback_received` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `received_negative_feedback_rate` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.11 `amazon_sales_traffic_asin_daily`

- 数据来源：GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByAsin
- 表用途：ASIN 维度销售、流量、转化率。
- 当前索引：`IX_amazon_sales_traffic_asin_daily_key`(marketplace_id, report_start_date DESC, report_end_date DESC, parent_asin, child_asin)；`IX_amazon_sales_traffic_asin_daily_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_start_date` | `DATE` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `report_end_date` | `DATE` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `parent_asin` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `child_asin` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `date_granularity` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `asin_granularity` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `ordered_product_sales_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `ordered_product_sales_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `ordered_product_sales_b2b_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `ordered_product_sales_b2b_currency` | `NVARCHAR(10)` | NULL |  | 金额字段对应币种。 |
| `units_ordered` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `units_ordered_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `total_order_items` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `total_order_items_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_page_views` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_page_views_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_page_views_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_page_views_percentage_b2b` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_page_views` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_page_views_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_page_views_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_page_views_percentage_b2b` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `page_views` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `page_views_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `page_views_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `page_views_percentage_b2b` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_sessions` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_sessions_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_session_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `browser_session_percentage_b2b` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_sessions` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_sessions_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_session_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `mobile_app_session_percentage_b2b` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sessions` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sessions_b2b` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `session_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `session_percentage_b2b` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `buy_box_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `buy_box_percentage_b2b` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `unit_session_percentage` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `unit_session_percentage_b2b` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.12 `amazon_settlement_transaction`

- 数据来源：GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2
- 表用途：实际入账财务明细、费用、退款、广告扣费、Coupon/Deal 费用、分类字段。
- 当前索引：`IX_amazon_settlement_transaction_settlement`(marketplace_id, settlement_id, is_settlement_summary, transaction_type)；`IX_amazon_settlement_transaction_order_sku`(marketplace_id, order_id, seller_sku, amount_category, profit_bucket)；`IX_amazon_settlement_transaction_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `settlement_id` | `NVARCHAR(200)` | NULL |  | 结算单 id。 |
| `settlement_start_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `settlement_end_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `deposit_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `total_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `currency` | `NVARCHAR(10)` | NULL |  | 币种。 |
| `is_settlement_summary` | `BIT` | NOT NULL | `0` | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `transaction_type` | `NVARCHAR(120)` | NULL |  | 结算交易类型。 |
| `order_id` | `NVARCHAR(200)` | NULL |  | 源系统或本系统标识字段。 |
| `merchant_order_id` | `NVARCHAR(200)` | NULL |  | 源系统或本系统标识字段。 |
| `adjustment_id` | `NVARCHAR(200)` | NULL |  | 源系统或本系统标识字段。 |
| `shipment_id` | `NVARCHAR(200)` | NULL |  | 源系统或本系统标识字段。 |
| `marketplace_name` | `NVARCHAR(200)` | NULL |  | 名称/标题字段。 |
| `amount_type` | `NVARCHAR(120)` | NULL |  | Amazon 结算 amount-type。 |
| `amount_description` | `NVARCHAR(300)` | NULL |  | Amazon 结算 amount-description。 |
| `amount` | `DECIMAL(18,4)` | NULL |  | 结算金额。 |
| `amount_category` | `NVARCHAR(120)` | NOT NULL |  | 本系统第一版金额分类。 |
| `profit_bucket` | `NVARCHAR(120)` | NOT NULL |  | 本系统第一版利润口径分桶。 |
| `fulfillment_id` | `NVARCHAR(100)` | NULL |  | 源系统或本系统标识字段。 |
| `posted_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `posted_date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `order_item_code` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `merchant_order_item_id` | `NVARCHAR(200)` | NULL |  | 源系统或本系统标识字段。 |
| `merchant_adjustment_item_id` | `NVARCHAR(200)` | NULL |  | 源系统或本系统标识字段。 |
| `seller_sku` | `NVARCHAR(200)` | NULL |  | 卖家 SKU。 |
| `quantity_purchased` | `INT` | NULL |  | 数量字段。 |
| `promotion_id` | `NVARCHAR(500)` | NULL |  | 促销活动 id。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.13 `amazon_order_item`

- 数据来源：GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL
- 表用途：订单/SKU 行、金额、税、促销、发货地区。
- 当前索引：`IX_amazon_order_item_order_sku`(marketplace_id, amazon_order_id, seller_sku, asin)；`IX_amazon_order_item_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `amazon_order_id` | `NVARCHAR(200)` | NULL |  | Amazon 订单号。 |
| `merchant_order_id` | `NVARCHAR(200)` | NULL |  | 源系统或本系统标识字段。 |
| `purchase_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `last_updated_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `order_status` | `NVARCHAR(100)` | NULL |  | 订单状态。 |
| `fulfillment_channel` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sales_channel` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `order_channel` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `ship_service_level` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `product_name` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `seller_sku` | `NVARCHAR(200)` | NULL |  | 卖家 SKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `item_status` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `quantity` | `INT` | NULL |  | 数量字段。 |
| `currency` | `NVARCHAR(10)` | NULL |  | 币种。 |
| `item_price` | `DECIMAL(18,4)` | NULL |  | 商品金额。 |
| `item_tax` | `DECIMAL(18,4)` | NULL |  | 商品税。 |
| `shipping_price` | `DECIMAL(18,4)` | NULL |  | 配送收入。 |
| `shipping_tax` | `DECIMAL(18,4)` | NULL |  | 配送税。 |
| `gift_wrap_price` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `gift_wrap_tax` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `item_promotion_discount` | `DECIMAL(18,4)` | NULL |  | 商品促销折扣。 |
| `ship_promotion_discount` | `DECIMAL(18,4)` | NULL |  | 配送促销折扣。 |
| `ship_city` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `ship_state` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `ship_postal_code` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `ship_country` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `promotion_ids` | `NVARCHAR(1000)` | NULL |  | 订单促销 id 列表。 |
| `is_business_order` | `BIT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `purchase_order_number` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `price_designation` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `signature_confirmation_recommended` | `BIT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.14 `amazon_fba_reimbursement`

- 数据来源：GET_FBA_REIMBURSEMENTS_DATA
- 表用途：赔偿原因、case、SKU、金额、现金/库存赔偿数量。
- 当前索引：`IX_amazon_fba_reimbursement_key`(marketplace_id, reimbursement_id, case_id, seller_sku, asin)；`IX_amazon_fba_reimbursement_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `approval_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `reimbursement_id` | `NVARCHAR(200)` | NULL |  | FBA reimbursement id。 |
| `case_id` | `NVARCHAR(200)` | NULL |  | FBA case id。 |
| `amazon_order_id` | `NVARCHAR(200)` | NULL |  | Amazon 订单号。 |
| `reason` | `NVARCHAR(300)` | NULL |  | 赔偿或库存事件原因。 |
| `seller_sku` | `NVARCHAR(200)` | NULL |  | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL |  | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `condition` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `currency` | `NVARCHAR(10)` | NULL |  | 币种。 |
| `amount_per_unit` | `DECIMAL(18,4)` | NULL |  | 单件赔偿金额。 |
| `amount_total` | `DECIMAL(18,4)` | NULL |  | 赔偿总金额。 |
| `quantity_reimbursed_cash` | `INT` | NULL |  | 现金赔偿件数。 |
| `quantity_reimbursed_inventory` | `INT` | NULL |  | 库存赔偿件数。 |
| `quantity_reimbursed_total` | `INT` | NULL |  | 赔偿总件数。 |
| `original_reimbursement_id` | `NVARCHAR(200)` | NULL |  | 源系统或本系统标识字段。 |
| `original_reimbursement_type` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.15 `amazon_fba_fee_preview`

- 数据来源：GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA
- 表用途：SKU 尺寸、重量、预估 referral/FBA fulfillment fee。
- 当前索引：`IX_amazon_fba_fee_preview_sku`(marketplace_id, seller_sku, fnsku, asin)；`IX_amazon_fba_fee_preview_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `seller_sku` | `NVARCHAR(200)` | NULL |  | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL |  | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `amazon_store` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `product_name` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `product_group` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `brand` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `fulfilled_by` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `your_price` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sales_price` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `longest_side` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `median_side` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `shortest_side` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `length_and_girth` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `unit_of_dimension` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `item_package_weight` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `unit_of_weight` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `product_size_tier` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `currency` | `NVARCHAR(10)` | NULL |  | 币种。 |
| `estimated_fee_total` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_referral_fee_per_unit` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_variable_closing_fee` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_order_handling_fee_per_order` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_pick_pack_fee_per_unit` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_weight_handling_fee_per_unit` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `expected_fulfillment_fee_per_unit` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_future_fee_total` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_future_order_handling_fee_per_order` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_future_pick_pack_fee_per_unit` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_future_weight_handling_fee_per_unit` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `expected_future_fulfillment_fee_per_unit` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.16 `amazon_inventory_ledger_summary_daily`

- 数据来源：GET_LEDGER_SUMMARY_VIEW_DATA
- 表用途：每日/地点维度仓库库存变动汇总。
- 当前索引：`IX_amazon_inventory_ledger_summary_daily_key`(marketplace_id, seller_sku, fnsku, asin, ledger_date_raw)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `ledger_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `fnsku` | `NVARCHAR(100)` | NULL |  | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `seller_sku` | `NVARCHAR(200)` | NULL |  | 卖家 SKU。 |
| `title` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `disposition` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `starting_warehouse_balance` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `in_transit_between_warehouses` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `receipts` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `customer_shipments` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `customer_returns` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `vendor_returns` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `warehouse_transfer_in_out` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `found` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `lost` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `damaged` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `disposed` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `other_events` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `ending_warehouse_balance` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `unknown_events` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `location` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `store` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.17 `amazon_inventory_ledger_detail`

- 数据来源：GET_LEDGER_DETAIL_VIEW_DATA
- 表用途：FBA 仓库事件明细、reference、数量、原因。
- 当前索引：`IX_amazon_inventory_ledger_detail_key`(marketplace_id, seller_sku, fnsku, asin, event_type, reference_id)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `ledger_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `fnsku` | `NVARCHAR(100)` | NULL |  | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `seller_sku` | `NVARCHAR(200)` | NULL |  | 卖家 SKU。 |
| `title` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `event_type` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `reference_id` | `NVARCHAR(300)` | NULL |  | 源系统或本系统标识字段。 |
| `quantity` | `INT` | NULL |  | 数量字段。 |
| `fulfillment_center` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `disposition` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `reason` | `NVARCHAR(300)` | NULL |  | 赔偿或库存事件原因。 |
| `country` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `reconciled_quantity` | `INT` | NULL |  | 数量字段。 |
| `unreconciled_quantity` | `INT` | NULL |  | 数量字段。 |
| `date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `store` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.18 `amazon_reserved_inventory_daily`

- 数据来源：GET_RESERVED_INVENTORY_DATA
- 表用途：预留数量按 customer orders / FC transfer / processing 拆分。
- 当前索引：`IX_amazon_reserved_inventory_daily_key`(marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `snapshot_date` | `DATE` | NOT NULL | `CONVERT(date, SYSUTCDATETIME())` | 库存/Listing 快照日期。 |
| `seller_sku` | `NVARCHAR(200)` | NULL |  | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL |  | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `reserved_quantity` | `INT` | NULL |  | 数量字段。 |
| `reserved_customer_orders` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `reserved_fc_transfers` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `reserved_fc_processing` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `program` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.19 `amazon_inventory_planning_daily`

- 数据来源：GET_FBA_INVENTORY_PLANNING_DATA / GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT
- 表用途：库龄、售罄率、days of supply、推荐动作。
- 当前索引：`IX_amazon_inventory_planning_daily_key`(marketplace_id, seller_sku, fnsku, asin, snapshot_date_raw)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `snapshot_date_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `seller_sku` | `NVARCHAR(200)` | NULL |  | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL |  | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `condition` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `available_quantity` | `INT` | NULL |  | 数量字段。 |
| `pending_removal_quantity` | `INT` | NULL |  | 数量字段。 |
| `inv_age_0_to_90_days` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `inv_age_91_to_180_days` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `inv_age_181_to_270_days` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `inv_age_271_to_365_days` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `inv_age_366_to_455_days` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `inv_age_456_plus_days` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `currency` | `NVARCHAR(10)` | NULL |  | 币种。 |
| `units_shipped_t7` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `units_shipped_t30` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `units_shipped_t60` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `units_shipped_t90` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `alert` | `NVARCHAR(300)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `your_price` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sales_price` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `recommended_action` | `NVARCHAR(500)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `recommended_sales_price` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `recommended_sale_duration_days` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `recommended_removal_quantity` | `INT` | NULL |  | 数量字段。 |
| `estimated_cost_savings_of_recommended_actions` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sell_through` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `item_volume` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `volume_unit_measurement` | `NVARCHAR(50)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `storage_type` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `storage_volume` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `marketplace_name` | `NVARCHAR(200)` | NULL |  | 名称/标题字段。 |
| `product_group` | `NVARCHAR(200)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sales_rank` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `days_of_supply` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `estimated_excess_quantity` | `INT` | NULL |  | 数量字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.20 `amazon_promotion_performance`

- 数据来源：GET_PROMOTION_PERFORMANCE_REPORT
- 表用途：活动总体浏览、销量、销售额、状态与时间。
- 当前索引：`IX_amazon_promotion_performance_key`(marketplace_id, promotion_id, status)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `promotion_id` | `NVARCHAR(200)` | NULL |  | 促销活动 id。 |
| `merchant_id` | `NVARCHAR(200)` | NULL |  | 商家 id。 |
| `promotion_name` | `NVARCHAR(500)` | NULL |  | 名称/标题字段。 |
| `promotion_type` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `status` | `NVARCHAR(100)` | NULL |  | 状态字段。 |
| `glance_views` | `INT` | NULL |  | 活动/商品浏览量。 |
| `units_sold` | `INT` | NULL |  | 活动销量。 |
| `revenue` | `DECIMAL(18,4)` | NULL |  | 活动销售额。 |
| `revenue_currency_code` | `NVARCHAR(10)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `start_date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `end_date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `created_date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `last_updated_date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.21 `amazon_promotion_product_performance`

- 数据来源：GET_PROMOTION_PERFORMANCE_REPORT.productPerformance
- 表用途：活动 ASIN 维度表现。
- 当前索引：`IX_amazon_promotion_product_performance_key`(marketplace_id, promotion_id, asin)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `promotion_id` | `NVARCHAR(200)` | NULL |  | 促销活动 id。 |
| `merchant_id` | `NVARCHAR(200)` | NULL |  | 商家 id。 |
| `promotion_name` | `NVARCHAR(500)` | NULL |  | 名称/标题字段。 |
| `promotion_type` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `status` | `NVARCHAR(100)` | NULL |  | 状态字段。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL |  | 名称/标题字段。 |
| `product_glance_views` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `product_units_sold` | `INT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `product_revenue` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `product_revenue_currency_code` | `NVARCHAR(10)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.22 `amazon_coupon_performance`

- 数据来源：GET_COUPON_PERFORMANCE_REPORT
- 表用途：Coupon 预算、领取、兑换、折扣、销售额。
- 当前索引：`IX_amazon_coupon_performance_key`(marketplace_id, coupon_id, merchant_id)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `coupon_id` | `NVARCHAR(200)` | NULL |  | Coupon id。 |
| `merchant_id` | `NVARCHAR(200)` | NULL |  | 商家 id。 |
| `currency_code` | `NVARCHAR(10)` | NULL |  | 币种代码。 |
| `name` | `NVARCHAR(500)` | NULL |  | 名称/标题字段。 |
| `website_message` | `NVARCHAR(1000)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `start_date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `end_date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `discount_type` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `discount_amount` | `DECIMAL(18,4)` | NULL |  | 金额字段。 |
| `total_discount` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `clips` | `INT` | NULL |  | Coupon 领取数。 |
| `redemptions` | `INT` | NULL |  | Coupon 兑换数。 |
| `budget` | `DECIMAL(18,4)` | NULL |  | Coupon 预算。 |
| `budget_spent` | `DECIMAL(18,4)` | NULL |  | Coupon 已用预算。 |
| `budget_remaining` | `DECIMAL(18,4)` | NULL |  | Coupon 剩余预算。 |
| `budget_percentage_used` | `DECIMAL(18,6)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `sales` | `DECIMAL(18,4)` | NULL |  | Coupon 归因销售额。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.23 `amazon_coupon_asin`

- 数据来源：GET_COUPON_PERFORMANCE_REPORT.asins
- 表用途：Coupon 关联 ASIN。
- 当前索引：`IX_amazon_coupon_asin_key`(marketplace_id, coupon_id, asin)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `coupon_id` | `NVARCHAR(200)` | NULL |  | Coupon id。 |
| `merchant_id` | `NVARCHAR(200)` | NULL |  | 商家 id。 |
| `asin` | `NVARCHAR(50)` | NULL |  | Amazon ASIN。 |
| `coupon_name` | `NVARCHAR(500)` | NULL |  | 名称/标题字段。 |
| `currency_code` | `NVARCHAR(10)` | NULL |  | 币种代码。 |
| `start_date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `end_date_time_raw` | `NVARCHAR(100)` | NULL |  | 源文件原始字符串字段，暂不强转，便于后续规则调整。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'sp_api_reports'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL |  | Listing 业务幂等键 hash；由 `003_add_listing_snapshot_business_key_hash.sql` 增加。Repository 写入业务行时应生成非空值，历史/过渡空值由过滤唯一索引兼容。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.24 `amazon_ads_profile`

- 数据来源：Amazon Ads Profiles API
- 表用途：profile、国家、币种、账户类型、支付状态。
- 当前索引：`UX_amazon_ads_profile_profile_id`(profile_id)；`IX_amazon_ads_profile_marketplace`(marketplace_id, country_code, account_type)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL |  | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `country_code` | `NVARCHAR(10)` | NULL |  | 国家代码。 |
| `currency_code` | `NVARCHAR(10)` | NULL |  | 币种代码。 |
| `timezone` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `account_id` | `NVARCHAR(100)` | NULL |  | 源系统或本系统标识字段。 |
| `account_type` | `NVARCHAR(100)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `account_name` | `NVARCHAR(500)` | NULL |  | 名称/标题字段。 |
| `valid_payment_method` | `BIT` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `daily_budget` | `DECIMAL(18,4)` | NULL |  | 按源报告字段语义保存；后续可在设计文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'amazon_ads'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `discovered_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 时间字段。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.25 `amazon_ads_sp_campaign_daily`

- 数据来源：Amazon Ads spCampaigns
- 表用途：SP campaign 日维度曝光、点击、花费、7日销售/购买。
- 当前索引：`IX_amazon_ads_sp_campaign_daily_key`(profile_id, report_date DESC, campaign_id)；`UX_amazon_ads_sp_campaign_daily_business_key`(business_key_hash)；`IX_amazon_ads_sp_campaign_daily_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL |  | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL |  | 报表日期。 |
| `campaign_id` | `NVARCHAR(100)` | NULL |  | 广告 campaign id。 |
| `campaign_name` | `NVARCHAR(500)` | NULL |  | 广告 campaign 名称。 |
| `campaign_status` | `NVARCHAR(100)` | NULL |  | 广告 campaign 状态。 |
| `impressions` | `INT` | NULL |  | 广告曝光数。 |
| `clicks` | `INT` | NULL |  | 广告点击数。 |
| `cost` | `DECIMAL(18,4)` | NULL |  | 广告花费。 |
| `sales_7d` | `DECIMAL(18,4)` | NULL |  | 广告点击后 7 天归因销售额。 |
| `purchases_7d` | `INT` | NULL |  | 广告点击后 7 天归因购买数。 |
| `units_sold_clicks_7d` | `INT` | NULL |  | 广告点击后 7 天归因售出件数。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'amazon_ads'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_index` | `INT` | NULL |  | raw report 中的行序号。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NOT NULL |  | 业务唯一键 hash，用于 MERGE/upsert。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.26 `amazon_ads_sp_targeting_daily`

- 数据来源：Amazon Ads spTargeting
- 表用途：关键词/target 日维度表现。
- 当前索引：`IX_amazon_ads_sp_targeting_daily_key`(profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id)；`UX_amazon_ads_sp_targeting_daily_business_key`(business_key_hash)；`IX_amazon_ads_sp_targeting_daily_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL |  | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL |  | 报表日期。 |
| `campaign_id` | `NVARCHAR(100)` | NULL |  | 广告 campaign id。 |
| `campaign_name` | `NVARCHAR(500)` | NULL |  | 广告 campaign 名称。 |
| `ad_group_id` | `NVARCHAR(100)` | NULL |  | 广告 ad group id。 |
| `ad_group_name` | `NVARCHAR(500)` | NULL |  | 广告 ad group 名称。 |
| `keyword_id` | `NVARCHAR(100)` | NULL |  | 广告 keyword id。 |
| `keyword` | `NVARCHAR(500)` | NULL |  | 广告关键词。 |
| `match_type` | `NVARCHAR(100)` | NULL |  | 广告匹配类型。 |
| `targeting` | `NVARCHAR(1000)` | NULL |  | 广告 targeting 表达式。 |
| `impressions` | `INT` | NULL |  | 广告曝光数。 |
| `clicks` | `INT` | NULL |  | 广告点击数。 |
| `cost` | `DECIMAL(18,4)` | NULL |  | 广告花费。 |
| `sales_7d` | `DECIMAL(18,4)` | NULL |  | 广告点击后 7 天归因销售额。 |
| `purchases_7d` | `INT` | NULL |  | 广告点击后 7 天归因购买数。 |
| `units_sold_clicks_7d` | `INT` | NULL |  | 广告点击后 7 天归因售出件数。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'amazon_ads'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_index` | `INT` | NULL |  | raw report 中的行序号。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NOT NULL |  | 业务唯一键 hash，用于 MERGE/upsert。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.27 `amazon_ads_sp_search_term_daily`

- 数据来源：Amazon Ads spSearchTerm
- 表用途：用户搜索词表现，用于加词/否词。
- 当前索引：`IX_amazon_ads_sp_search_term_daily_key`(profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id)；`UX_amazon_ads_sp_search_term_daily_business_key`(business_key_hash)；`IX_amazon_ads_sp_search_term_daily_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL |  | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL |  | 报表日期。 |
| `campaign_id` | `NVARCHAR(100)` | NULL |  | 广告 campaign id。 |
| `campaign_name` | `NVARCHAR(500)` | NULL |  | 广告 campaign 名称。 |
| `ad_group_id` | `NVARCHAR(100)` | NULL |  | 广告 ad group id。 |
| `ad_group_name` | `NVARCHAR(500)` | NULL |  | 广告 ad group 名称。 |
| `keyword_id` | `NVARCHAR(100)` | NULL |  | 广告 keyword id。 |
| `keyword` | `NVARCHAR(500)` | NULL |  | 广告关键词。 |
| `match_type` | `NVARCHAR(100)` | NULL |  | 广告匹配类型。 |
| `targeting` | `NVARCHAR(1000)` | NULL |  | 广告 targeting 表达式。 |
| `search_term` | `NVARCHAR(1000)` | NULL |  | 用户真实搜索词。 |
| `impressions` | `INT` | NULL |  | 广告曝光数。 |
| `clicks` | `INT` | NULL |  | 广告点击数。 |
| `cost` | `DECIMAL(18,4)` | NULL |  | 广告花费。 |
| `sales_7d` | `DECIMAL(18,4)` | NULL |  | 广告点击后 7 天归因销售额。 |
| `purchases_7d` | `INT` | NULL |  | 广告点击后 7 天归因购买数。 |
| `units_sold_clicks_7d` | `INT` | NULL |  | 广告点击后 7 天归因售出件数。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'amazon_ads'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_index` | `INT` | NULL |  | raw report 中的行序号。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NOT NULL |  | 业务唯一键 hash，用于 MERGE/upsert。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

### 4.28 `amazon_ads_sp_advertised_product_daily`

- 数据来源：Amazon Ads spAdvertisedProduct
- 表用途：广告 SKU/ASIN 日维度表现。
- 当前索引：`IX_amazon_ads_sp_advertised_product_daily_key`(profile_id, report_date DESC, advertised_asin, advertised_sku)；`UX_amazon_ads_sp_advertised_product_daily_business_key`(business_key_hash)；`IX_amazon_ads_sp_advertised_product_daily_campaign`(profile_id, campaign_id, ad_group_id, report_date DESC)；`IX_amazon_ads_sp_advertised_product_daily_source`(source_report_id, source_row_hash)

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL |  | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL |  | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL |  | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL |  | 报表日期。 |
| `campaign_id` | `NVARCHAR(100)` | NULL |  | 广告 campaign id。 |
| `campaign_name` | `NVARCHAR(500)` | NULL |  | 广告 campaign 名称。 |
| `ad_group_id` | `NVARCHAR(100)` | NULL |  | 广告 ad group id。 |
| `ad_group_name` | `NVARCHAR(500)` | NULL |  | 广告 ad group 名称。 |
| `advertised_asin` | `NVARCHAR(50)` | NULL |  | 广告投放 ASIN。 |
| `advertised_sku` | `NVARCHAR(200)` | NULL |  | 广告投放 SKU。 |
| `impressions` | `INT` | NULL |  | 广告曝光数。 |
| `clicks` | `INT` | NULL |  | 广告点击数。 |
| `cost` | `DECIMAL(18,4)` | NULL |  | 广告花费。 |
| `sales_7d` | `DECIMAL(18,4)` | NULL |  | 广告点击后 7 天归因销售额。 |
| `purchases_7d` | `INT` | NULL |  | 广告点击后 7 天归因购买数。 |
| `units_sold_clicks_7d` | `INT` | NULL |  | 广告点击后 7 天归因售出件数。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `'amazon_ads'` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL |  | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL |  | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL |  | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL |  | 本系统 raw file 归档表 id；当前 Ads 首轮尚为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL |  | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL |  | 对应 amazon_sync_run_log.id。 |
| `source_row_index` | `INT` | NULL |  | raw report 中的行序号。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL |  | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NOT NULL |  | 业务唯一键 hash，用于 MERGE/upsert。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL |  | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2` | NOT NULL | `SYSUTCDATETIME()` | 数据库记录最后更新时间 UTC。 |

