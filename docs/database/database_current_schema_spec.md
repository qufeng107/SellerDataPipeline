# SellerDataPipeline 当前真实数据库 Schema Spec

> 文档版本：v1.13  
> 更新日期：2026-05-18  
> 文档定位：**当前真实实现记录**。本文件只记录已经在 Azure SQL `amazon_ops` 执行成功的表、字段、索引与数据来源；不写未来设计。设计变更请先更新对应的 `docs/features/feature_*.md` 或 `docs/data_access/*.md`；如涉及库结构变化，先对比本文件，再新增 migration；migration 执行成功后优先运行 `scripts/export_database_schema_spec.py` 导出 live schema snapshot，再更新本文件。

## 1. 当前数据库状态

| 项目 | 当前值 |
|---|---|
| Azure SQL database | `amazon_ops` |
| Server | `amazon-ops-sql` |
| 已执行 migration | `001_create_core_tables.sql` 29/29 batches；`002_create_indexes.sql` 54/54 batches；`003_add_listing_snapshot_business_key_hash.sql` 3/3 batches；`004_add_inventory_daily_business_key_hash.sql` 3/3 batches；`005_add_sales_traffic_business_key_hashes.sql` 5/5 batches；`006_add_settlement_transaction_business_key.sql` 4/4 batches；`007_add_order_item_business_key.sql` 4/4 batches；`008_add_fba_reimbursement_business_key.sql` 4/4 batches；`009_add_fba_fee_preview_business_key.sql` 4/4 batches；`010_add_promotion_coupon_business_keys.sql` 8/8 batches；`011_add_inventory_ledger_business_keys.sql` 4/4 batches；`012_create_ingestion_job_config.sql` 4/4 batches；`001_seed_ingestion_job_config_core_jobs.sql` 1/1 batch |
| 用户表数量 | 29 |
| 已真实入库验证 | Amazon Ads 4 张 SP 日表，首次 inserted=200、重复执行 inserted=0/updated=200；Listing 快照表首次 inserted=6、重复执行 inserted=0/updated=6；Inventory 快照表首次 inserted=5、重复执行 inserted=0/updated=5；Sales & Traffic 首次 inserted=7、重复执行 inserted=0/updated=7；Settlement 首次 inserted=4911、重复执行 inserted=0/updated=4911；Orders 首次 inserted=112、重复执行 inserted=0/updated=112；FBA Reimbursements 首次 inserted=19、重复执行 inserted=0/updated=19；FBA Fee Preview 首次 inserted=8、重复执行 inserted=0/updated=8；Promotion/Coupon 首次 inserted=10、重复执行 inserted=0/updated=10；Inventory Ledger 首次 inserted=357、重复执行 inserted=0/updated=357 |
| 当前限制 | `amazon_sync_run_log` 尚无 rows_inserted / rows_updated 字段；normalized 表当前 `source_raw_file_id` 仍可能为 NULL；`pipeline_job_config` 已创建并 seed 13 条任务配置，其中利润、周报、邮件任务仍是 disabled placeholder，待功能实现后再启用 |

## 1.1 最新执行记录

`012_create_ingestion_job_config.sql` 已在 Azure SQL `amazon_ops` 执行成功，执行结果为 4/4 batches。随后 `sql/seeds/001_seed_ingestion_job_config_core_jobs.sql` 已执行成功，执行结果为 1/1 batch。

最新 live schema 已导出到：

```text
runtime/schema_exports/after_012_job_config.json
runtime/schema_exports/after_012_job_config.md
```

导出结果显示当前用户表数量为 29，`pipeline_job_config` 当前行数为 13。

## 1.2 Schema 更新辅助工具

后续 migration 执行成功后，优先使用以下命令从真实 Azure SQL 导出 schema snapshot：

```bash
python scripts/export_database_schema_spec.py --output-prefix after_NNN_xxx --include-row-counts
```

导出结果用于辅助更新本文件，但不能自动替代本文件。原因是本文件还需要维护字段业务说明、数据来源、真实入库状态和已知限制。工具说明见：`docs/database/database_schema_export_tool.md`。

## 2. 表清单与数据来源

| 表 | 类型 | 数据来源 | 说明 |
|---|---|---|---|
| `amazon_ads_profile` | Ads profile | Amazon Ads Profiles API | profile、国家、币种、账户类型、支付状态。 |
| `amazon_ads_sp_advertised_product_daily` | 广告 advertised product 日表 | Amazon Ads spAdvertisedProduct | 广告 SKU/ASIN 日维度表现。 |
| `amazon_ads_sp_campaign_daily` | 广告 campaign 日表 | Amazon Ads spCampaigns | SP campaign 日维度曝光、点击、花费、7日销售/购买。 |
| `amazon_ads_sp_search_term_daily` | 广告 search term 日表 | Amazon Ads spSearchTerm | 用户搜索词表现，用于加词/否词。 |
| `amazon_ads_sp_targeting_daily` | 广告 targeting 日表 | Amazon Ads spTargeting | 关键词/target 日维度表现。 |
| `amazon_coupon_asin` | Coupon ASIN | GET_COUPON_PERFORMANCE_REPORT.asins | Coupon 关联 ASIN。 |
| `amazon_coupon_performance` | Coupon 主表 | GET_COUPON_PERFORMANCE_REPORT | Coupon 预算、领取、兑换、折扣、销售额。 |
| `amazon_fba_fee_preview` | FBA 费用预估 | GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA | SKU 尺寸、重量、预估 referral/FBA fulfillment fee。 |
| `amazon_fba_reimbursement` | FBA 赔偿 | GET_FBA_REIMBURSEMENTS_DATA | 赔偿原因、case、SKU、金额、现金/库存赔偿数量。 |
| `amazon_inventory_daily` | 库存快照 | GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA | FBA 可售、不可售、预留、入库、研究中等库存数量。 |
| `amazon_inventory_ledger_detail` | 库存流水明细 | GET_LEDGER_DETAIL_VIEW_DATA | FBA 仓库事件明细、reference、数量、原因。 |
| `amazon_inventory_ledger_summary_daily` | 库存流水汇总 | GET_LEDGER_SUMMARY_VIEW_DATA | 每日/地点维度仓库库存变动汇总。 |
| `amazon_inventory_planning_daily` | 库存健康/补货 | GET_FBA_INVENTORY_PLANNING_DATA / GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT | 库龄、售罄率、days of supply、推荐动作。 |
| `amazon_listing_snapshot` | Listing 快照 | GET_MERCHANT_LISTINGS_ALL_DATA | SKU/ASIN/listing 状态、标题、价格、履约渠道。 |
| `amazon_marketplace` | 基础维表 | 手工 seed / Amazon marketplace metadata | 市场、币种、SP-API endpoint。 |
| `amazon_order_item` | 订单明细 | GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL | 订单/SKU 行、金额、税、促销、发货地区。 |
| `amazon_promotion_performance` | 促销主表 | GET_PROMOTION_PERFORMANCE_REPORT | 活动总体浏览、销量、销售额、状态与时间。 |
| `amazon_promotion_product_performance` | 促销商品明细 | GET_PROMOTION_PERFORMANCE_REPORT.productPerformance | 活动 ASIN 维度表现。 |
| `amazon_raw_report_file` | raw 归档 | 所有 Amazon SP-API / Ads raw files | 原始文件路径、hash、行列数、编码、下载时间。 |
| `amazon_report_field_catalog` | 字段目录 | 字段取样/分析脚本 | 观察到的源字段、目标表/字段建议、样例值。 |
| `amazon_report_request` | 请求控制 | SP-API Reports createReport/getReports | 报告请求、状态、document id、下载/解析状态。 |
| `amazon_reserved_inventory_daily` | 预留库存 | GET_RESERVED_INVENTORY_DATA | 预留数量按 customer orders / FC transfer / processing 拆分。 |
| `amazon_sales_traffic_asin_daily` | 销售流量-ASIN | GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByAsin | ASIN 维度销售、流量、转化率。 |
| `amazon_sales_traffic_daily` | 销售流量-日期 | GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByDate | 日期维度销售额、订单、退款、sessions、page views、转化率。 |
| `amazon_schema_validation_event` | schema 守门 | 下载后/入库前 schema validation | 字段漂移、缺字段、新字段、requires_review 和通知状态。 |
| `amazon_settlement_transaction` | 结算明细 | GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2 | 实际入账财务明细、费用、退款、广告扣费、Coupon/Deal 费用、分类字段。 |
| `amazon_sku_cost` | 成本配置 | 手工维护/会计成本输入 | SKU 采购、头程、包装等单位成本。 |
| `amazon_sync_run_log` | 审计控制 | 所有采集/解析/入库任务 | 任务运行状态、行数、耗时、错误信息。 |
| `pipeline_job_config` | 任务配置 | 手动 seed / 未来自动化配置 | 数据下载、入库、加工、报表和邮件任务的周期、脚本路径、默认参数和执行阶段。 |

## 3. 索引清单

| 表 | 索引 | 唯一 | 字段 | 过滤条件 |
|---|---|---|---|---|
| `amazon_ads_profile` | `IX_amazon_ads_profile_marketplace` | 否 | `marketplace_id, country_code, account_type` | `` |
| `amazon_ads_profile` | `UX_amazon_ads_profile_profile_id` | 是 | `profile_id` | `` |
| `amazon_ads_sp_advertised_product_daily` | `IX_amazon_ads_sp_advertised_product_daily_campaign` | 否 | `profile_id, campaign_id, ad_group_id, report_date DESC` | `` |
| `amazon_ads_sp_advertised_product_daily` | `IX_amazon_ads_sp_advertised_product_daily_key` | 否 | `profile_id, report_date DESC, advertised_asin, advertised_sku` | `` |
| `amazon_ads_sp_advertised_product_daily` | `IX_amazon_ads_sp_advertised_product_daily_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_ads_sp_advertised_product_daily` | `UX_amazon_ads_sp_advertised_product_daily_business_key` | 是 | `business_key_hash` | `` |
| `amazon_ads_sp_campaign_daily` | `IX_amazon_ads_sp_campaign_daily_key` | 否 | `profile_id, report_date DESC, campaign_id` | `` |
| `amazon_ads_sp_campaign_daily` | `IX_amazon_ads_sp_campaign_daily_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_ads_sp_campaign_daily` | `UX_amazon_ads_sp_campaign_daily_business_key` | 是 | `business_key_hash` | `` |
| `amazon_ads_sp_search_term_daily` | `IX_amazon_ads_sp_search_term_daily_key` | 否 | `profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id` | `` |
| `amazon_ads_sp_search_term_daily` | `IX_amazon_ads_sp_search_term_daily_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_ads_sp_search_term_daily` | `UX_amazon_ads_sp_search_term_daily_business_key` | 是 | `business_key_hash` | `` |
| `amazon_ads_sp_targeting_daily` | `IX_amazon_ads_sp_targeting_daily_key` | 否 | `profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id` | `` |
| `amazon_ads_sp_targeting_daily` | `IX_amazon_ads_sp_targeting_daily_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_ads_sp_targeting_daily` | `UX_amazon_ads_sp_targeting_daily_business_key` | 是 | `business_key_hash` | `` |
| `amazon_coupon_asin` | `IX_amazon_coupon_asin_key` | 否 | `marketplace_id, coupon_id, asin` | `` |
| `amazon_coupon_asin` | `UX_amazon_coupon_asin_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_coupon_performance` | `IX_amazon_coupon_performance_key` | 否 | `marketplace_id, coupon_id, merchant_id` | `` |
| `amazon_coupon_performance` | `UX_amazon_coupon_performance_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_fba_fee_preview` | `IX_amazon_fba_fee_preview_sku` | 否 | `marketplace_id, seller_sku, fnsku, asin` | `` |
| `amazon_fba_fee_preview` | `IX_amazon_fba_fee_preview_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_fba_fee_preview` | `UX_amazon_fba_fee_preview_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_fba_reimbursement` | `IX_amazon_fba_reimbursement_key` | 否 | `marketplace_id, reimbursement_id, case_id, seller_sku, asin` | `` |
| `amazon_fba_reimbursement` | `IX_amazon_fba_reimbursement_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_fba_reimbursement` | `UX_amazon_fba_reimbursement_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_inventory_daily` | `IX_amazon_inventory_daily_key` | 否 | `marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin` | `` |
| `amazon_inventory_daily` | `IX_amazon_inventory_daily_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_inventory_daily` | `UX_amazon_inventory_daily_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_inventory_ledger_detail` | `IX_amazon_inventory_ledger_detail_key` | 否 | `marketplace_id, seller_sku, fnsku, asin, event_type, reference_id` | `` |
| `amazon_inventory_ledger_detail` | `UX_amazon_inventory_ledger_detail_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_inventory_ledger_summary_daily` | `IX_amazon_inventory_ledger_summary_daily_key` | 否 | `marketplace_id, seller_sku, fnsku, asin, ledger_date_raw` | `` |
| `amazon_inventory_ledger_summary_daily` | `UX_amazon_inventory_ledger_summary_daily_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_inventory_planning_daily` | `IX_amazon_inventory_planning_daily_key` | 否 | `marketplace_id, seller_sku, fnsku, asin, snapshot_date_raw` | `` |
| `amazon_listing_snapshot` | `IX_amazon_listing_snapshot_key` | 否 | `marketplace_id, snapshot_date DESC, seller_sku, listing_id` | `` |
| `amazon_listing_snapshot` | `IX_amazon_listing_snapshot_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_listing_snapshot` | `UX_amazon_listing_snapshot_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_marketplace` | `UX_amazon_marketplace_marketplace_id` | 是 | `marketplace_id` | `` |
| `amazon_order_item` | `IX_amazon_order_item_order_sku` | 否 | `marketplace_id, amazon_order_id, seller_sku, asin` | `` |
| `amazon_order_item` | `IX_amazon_order_item_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_order_item` | `UX_amazon_order_item_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_promotion_performance` | `IX_amazon_promotion_performance_key` | 否 | `marketplace_id, promotion_id, status` | `` |
| `amazon_promotion_performance` | `UX_amazon_promotion_performance_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_promotion_product_performance` | `IX_amazon_promotion_product_performance_key` | 否 | `marketplace_id, promotion_id, asin` | `` |
| `amazon_promotion_product_performance` | `UX_amazon_promotion_product_performance_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_raw_report_file` | `IX_amazon_raw_report_file_report` | 否 | `source_system, report_type, marketplace_id, downloaded_at DESC` | `` |
| `amazon_raw_report_file` | `IX_amazon_raw_report_file_sha256` | 否 | `sha256` | `` |
| `amazon_raw_report_file` | `UX_amazon_raw_report_file_path` | 是 | `storage_backend, file_path` | `` |
| `amazon_report_field_catalog` | `IX_amazon_report_field_catalog_report` | 否 | `source_system, report_type, marketplace_id, field_position` | `` |
| `amazon_report_request` | `IX_amazon_report_request_status` | 否 | `processing_status, download_status, parse_status, requested_at DESC` | `` |
| `amazon_report_request` | `IX_amazon_report_request_type_range` | 否 | `source_system, report_type, marketplace_id, data_start_time, data_end_time` | `` |
| `amazon_report_request` | `UX_amazon_report_request_report_id` | 是 | `marketplace_id, source_system, report_type, report_id` | `([report_id] IS NOT NULL)` |
| `amazon_reserved_inventory_daily` | `IX_amazon_reserved_inventory_daily_key` | 否 | `marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin` | `` |
| `amazon_sales_traffic_asin_daily` | `IX_amazon_sales_traffic_asin_daily_key` | 否 | `marketplace_id, report_start_date DESC, report_end_date DESC, parent_asin, child_asin` | `` |
| `amazon_sales_traffic_asin_daily` | `IX_amazon_sales_traffic_asin_daily_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_sales_traffic_asin_daily` | `UX_amazon_sales_traffic_asin_daily_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_sales_traffic_daily` | `IX_amazon_sales_traffic_daily_date` | 否 | `marketplace_id, report_date DESC` | `` |
| `amazon_sales_traffic_daily` | `IX_amazon_sales_traffic_daily_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_sales_traffic_daily` | `UX_amazon_sales_traffic_daily_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_schema_validation_event` | `IX_amazon_schema_validation_event_report` | 否 | `source_system, report_type, marketplace_id, created_at DESC` | `` |
| `amazon_schema_validation_event` | `IX_amazon_schema_validation_event_review` | 否 | `requires_review, notification_status, created_at DESC` | `` |
| `amazon_settlement_transaction` | `IX_amazon_settlement_transaction_order_sku` | 否 | `marketplace_id, order_id, seller_sku, amount_category, profit_bucket` | `` |
| `amazon_settlement_transaction` | `IX_amazon_settlement_transaction_settlement` | 否 | `marketplace_id, settlement_id, is_settlement_summary, transaction_type` | `` |
| `amazon_settlement_transaction` | `IX_amazon_settlement_transaction_source` | 否 | `source_report_id, source_row_hash` | `` |
| `amazon_settlement_transaction` | `UX_amazon_settlement_transaction_business_key_hash` | 是 | `business_key_hash` | `([business_key_hash] IS NOT NULL)` |
| `amazon_sku_cost` | `IX_amazon_sku_cost_effective` | 否 | `marketplace_id, seller_sku, effective_from, effective_to` | `` |
| `amazon_sync_run_log` | `IX_amazon_sync_run_log_job_started` | 否 | `job_name, started_at DESC` | `` |
| `amazon_sync_run_log` | `IX_amazon_sync_run_log_status_started` | 否 | `status, started_at DESC` | `` |
| `amazon_sync_run_log` | `IX_amazon_sync_run_log_workflow_started` | 否 | `workflow_name, started_at DESC` | `` |
| `pipeline_job_config` | `IX_pipeline_job_config_enabled_phase` | 否 | `enabled, execution_phase, job_group, manual_run_order` | `` |
| `pipeline_job_config` | `IX_pipeline_job_config_marketplace_domain` | 否 | `marketplace_id, data_domain, job_group` | `` |
| `pipeline_job_config` | `UX_pipeline_job_config_job_key` | 是 | `job_key` | `` |

## 4. 字段结构

### 4.1 `amazon_ads_profile`

- 数据来源：Amazon Ads Profiles API
- 表用途：profile、国家、币种、账户类型、支付状态。
- 当前索引：`IX_amazon_ads_profile_marketplace`(marketplace_id, country_code, account_type)；`UX_amazon_ads_profile_profile_id`(profile_id)
- 当前行数：`0`
- 行数说明：基于 `runtime/schema_exports/after_012_job_config` live schema 导出；如需刷新 row count，可重新运行 `scripts/export_database_schema_spec.py --include-row-counts`。

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL | `` | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `country_code` | `NVARCHAR(10)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `currency_code` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `timezone` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `account_id` | `NVARCHAR(100)` | NULL | `` | 源系统或本系统标识字段。 |
| `account_type` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `account_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `valid_payment_method` | `BIT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `daily_budget` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('amazon_ads')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `discovered_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 时间字段。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.2 `amazon_ads_sp_advertised_product_daily`

- 数据来源：Amazon Ads spAdvertisedProduct
- 表用途：广告 SKU/ASIN 日维度表现。
- 当前索引：`IX_amazon_ads_sp_advertised_product_daily_campaign`(profile_id, campaign_id, ad_group_id, report_date DESC)；`IX_amazon_ads_sp_advertised_product_daily_key`(profile_id, report_date DESC, advertised_asin, advertised_sku)；`IX_amazon_ads_sp_advertised_product_daily_source`(source_report_id, source_row_hash)；`UX_amazon_ads_sp_advertised_product_daily_business_key`(business_key_hash)
- 当前行数：`32`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL | `` | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL | `` | 报表日期。 |
| `campaign_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads campaign id。 |
| `campaign_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `ad_group_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads ad group id。 |
| `ad_group_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `advertised_asin` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `advertised_sku` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `impressions` | `INT` | NULL | `` | 广告曝光量。 |
| `clicks` | `INT` | NULL | `` | 广告点击量。 |
| `cost` | `DECIMAL(18,4)` | NULL | `` | 广告花费。 |
| `sales_7d` | `DECIMAL(18,4)` | NULL | `` | 广告 7 天归因销售额。 |
| `purchases_7d` | `INT` | NULL | `` | 广告 7 天归因购买数。 |
| `units_sold_clicks_7d` | `INT` | NULL | `` | 数量字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('amazon_ads')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_index` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NOT NULL | `` | 业务幂等键 hash，用于 MERGE/upsert。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.3 `amazon_ads_sp_campaign_daily`

- 数据来源：Amazon Ads spCampaigns
- 表用途：SP campaign 日维度曝光、点击、花费、7日销售/购买。
- 当前索引：`IX_amazon_ads_sp_campaign_daily_key`(profile_id, report_date DESC, campaign_id)；`IX_amazon_ads_sp_campaign_daily_source`(source_report_id, source_row_hash)；`UX_amazon_ads_sp_campaign_daily_business_key`(business_key_hash)
- 当前行数：`8`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL | `` | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL | `` | 报表日期。 |
| `campaign_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads campaign id。 |
| `campaign_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `campaign_status` | `NVARCHAR(100)` | NULL | `` | 状态字段。 |
| `impressions` | `INT` | NULL | `` | 广告曝光量。 |
| `clicks` | `INT` | NULL | `` | 广告点击量。 |
| `cost` | `DECIMAL(18,4)` | NULL | `` | 广告花费。 |
| `sales_7d` | `DECIMAL(18,4)` | NULL | `` | 广告 7 天归因销售额。 |
| `purchases_7d` | `INT` | NULL | `` | 广告 7 天归因购买数。 |
| `units_sold_clicks_7d` | `INT` | NULL | `` | 数量字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('amazon_ads')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_index` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NOT NULL | `` | 业务幂等键 hash，用于 MERGE/upsert。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.4 `amazon_ads_sp_search_term_daily`

- 数据来源：Amazon Ads spSearchTerm
- 表用途：用户搜索词表现，用于加词/否词。
- 当前索引：`IX_amazon_ads_sp_search_term_daily_key`(profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id)；`IX_amazon_ads_sp_search_term_daily_source`(source_report_id, source_row_hash)；`UX_amazon_ads_sp_search_term_daily_business_key`(business_key_hash)
- 当前行数：`61`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL | `` | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL | `` | 报表日期。 |
| `campaign_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads campaign id。 |
| `campaign_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `ad_group_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads ad group id。 |
| `ad_group_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `keyword_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads keyword/target id。 |
| `keyword` | `NVARCHAR(500)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `match_type` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `targeting` | `NVARCHAR(1000)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `search_term` | `NVARCHAR(1000)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `impressions` | `INT` | NULL | `` | 广告曝光量。 |
| `clicks` | `INT` | NULL | `` | 广告点击量。 |
| `cost` | `DECIMAL(18,4)` | NULL | `` | 广告花费。 |
| `sales_7d` | `DECIMAL(18,4)` | NULL | `` | 广告 7 天归因销售额。 |
| `purchases_7d` | `INT` | NULL | `` | 广告 7 天归因购买数。 |
| `units_sold_clicks_7d` | `INT` | NULL | `` | 数量字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('amazon_ads')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_index` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NOT NULL | `` | 业务幂等键 hash，用于 MERGE/upsert。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.5 `amazon_ads_sp_targeting_daily`

- 数据来源：Amazon Ads spTargeting
- 表用途：关键词/target 日维度表现。
- 当前索引：`IX_amazon_ads_sp_targeting_daily_key`(profile_id, report_date DESC, campaign_id, ad_group_id, keyword_id)；`IX_amazon_ads_sp_targeting_daily_source`(source_report_id, source_row_hash)；`UX_amazon_ads_sp_targeting_daily_business_key`(business_key_hash)
- 当前行数：`99`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `profile_id` | `NVARCHAR(100)` | NOT NULL | `` | Amazon Ads profile id。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL | `` | 报表日期。 |
| `campaign_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads campaign id。 |
| `campaign_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `ad_group_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads ad group id。 |
| `ad_group_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `keyword_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads keyword/target id。 |
| `keyword` | `NVARCHAR(500)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `match_type` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `targeting` | `NVARCHAR(1000)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `impressions` | `INT` | NULL | `` | 广告曝光量。 |
| `clicks` | `INT` | NULL | `` | 广告点击量。 |
| `cost` | `DECIMAL(18,4)` | NULL | `` | 广告花费。 |
| `sales_7d` | `DECIMAL(18,4)` | NULL | `` | 广告 7 天归因销售额。 |
| `purchases_7d` | `INT` | NULL | `` | 广告 7 天归因购买数。 |
| `units_sold_clicks_7d` | `INT` | NULL | `` | 数量字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('amazon_ads')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_index` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `business_key_hash` | `NVARCHAR(100)` | NOT NULL | `` | 业务幂等键 hash，用于 MERGE/upsert。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.6 `amazon_coupon_asin`

- 数据来源：GET_COUPON_PERFORMANCE_REPORT.asins
- 表用途：Coupon 关联 ASIN。
- 当前索引：`IX_amazon_coupon_asin_key`(marketplace_id, coupon_id, asin)；`UX_amazon_coupon_asin_business_key_hash`(business_key_hash, unique filtered)
- 当前行数：`4`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `coupon_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `merchant_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `coupon_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `currency_code` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `start_date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `end_date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `source_row_index` | `INT` | NULL | `` | 010/011 migration 新增；raw file 内 1-based 数据行号，用于行级追溯。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 010/011 migration 新增；业务幂等键 hash，用于 MERGE/upsert。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.7 `amazon_coupon_performance`

- 数据来源：GET_COUPON_PERFORMANCE_REPORT
- 表用途：Coupon 预算、领取、兑换、折扣、销售额。
- 当前索引：`IX_amazon_coupon_performance_key`(marketplace_id, coupon_id, merchant_id)
- 当前行数：`2`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `coupon_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `merchant_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `currency_code` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `website_message` | `NVARCHAR(1000)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `start_date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `end_date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `discount_type` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `discount_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `total_discount` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `clips` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `redemptions` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `budget` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `budget_spent` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `budget_remaining` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `budget_percentage_used` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `sales` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `source_row_index` | `INT` | NULL | `` | 010/011 migration 新增；raw file 内 1-based 数据行号，用于行级追溯。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 010/011 migration 新增；业务幂等键 hash，用于 MERGE/upsert。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.8 `amazon_fba_fee_preview`

- 数据来源：GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA
- 表用途：SKU 尺寸、重量、预估 referral/FBA fulfillment fee。
- 当前索引：`IX_amazon_fba_fee_preview_sku`(marketplace_id, seller_sku, fnsku, asin)；`IX_amazon_fba_fee_preview_source`(source_report_id, source_row_hash)；`UX_amazon_fba_fee_preview_business_key_hash`(business_key_hash)
- 当前行数：`8`
- 当前状态：`009_add_fba_fee_preview_business_key.sql` 已执行成功，字段与唯一过滤索引已存在；FBA Fee Preview 专用 ingestion 已完成 dry-run、首次 execute 与第二次 execute 幂等性验证。

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `seller_sku` | `NVARCHAR(200)` | NULL | `` | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL | `` | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `amazon_store` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `product_name` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `product_group` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `brand` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `fulfilled_by` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `your_price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `sales_price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `longest_side` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `median_side` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `shortest_side` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `length_and_girth` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `unit_of_dimension` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `item_package_weight` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `unit_of_weight` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `product_size_tier` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `currency` | `NVARCHAR(10)` | NULL | `` | 币种。 |
| `estimated_fee_total` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_referral_fee_per_unit` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_variable_closing_fee` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_order_handling_fee_per_order` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_pick_pack_fee_per_unit` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_weight_handling_fee_per_unit` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `expected_fulfillment_fee_per_unit` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_future_fee_total` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_future_order_handling_fee_per_order` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_future_pick_pack_fee_per_unit` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_future_weight_handling_fee_per_unit` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `expected_future_fulfillment_fee_per_unit` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.9 `amazon_fba_reimbursement`

- 数据来源：GET_FBA_REIMBURSEMENTS_DATA
- 表用途：赔偿原因、case、SKU、金额、现金/库存赔偿数量。
- 当前索引：`IX_amazon_fba_reimbursement_key`(marketplace_id, reimbursement_id, case_id, seller_sku, asin)；`IX_amazon_fba_reimbursement_source`(source_report_id, source_row_hash)；`UX_amazon_fba_reimbursement_business_key_hash`(business_key_hash)
- 当前行数：`19`
- 当前状态：`008_add_fba_reimbursement_business_key.sql` 已执行成功，字段与唯一过滤索引已存在；FBA Reimbursements 专用 ingestion 已完成 dry-run、首次 execute 和第二次 execute 幂等性验证。

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `approval_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `reimbursement_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `case_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `amazon_order_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `reason` | `NVARCHAR(300)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `seller_sku` | `NVARCHAR(200)` | NULL | `` | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL | `` | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `condition` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `currency` | `NVARCHAR(10)` | NULL | `` | 币种。 |
| `amount_per_unit` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `amount_total` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `quantity_reimbursed_cash` | `INT` | NULL | `` | 数量字段。 |
| `quantity_reimbursed_inventory` | `INT` | NULL | `` | 数量字段。 |
| `quantity_reimbursed_total` | `INT` | NULL | `` | 数量字段。 |
| `original_reimbursement_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `original_reimbursement_type` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |
| `source_row_index` | `INT` | NULL | `` | 源文件内 1-based data row index，用于行级追溯。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 业务幂等键 hash，用于 MERGE/upsert。 |

### 4.10 `amazon_inventory_daily`

- 数据来源：GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA
- 表用途：FBA 可售、不可售、预留、入库、研究中等库存数量。
- 当前索引：`IX_amazon_inventory_daily_key`(marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin)；`IX_amazon_inventory_daily_source`(source_report_id, source_row_hash)；`UX_amazon_inventory_daily_business_key_hash`(business_key_hash)
- 当前行数：`5`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `snapshot_date` | `DATE` | NOT NULL | `` | 库存/Listing 快照日期。 |
| `seller_sku` | `NVARCHAR(200)` | NOT NULL | `` | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL | `` | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `condition` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `your_price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `currency` | `NVARCHAR(10)` | NULL | `` | 币种。 |
| `mfn_listing_exists` | `BIT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mfn_fulfillable_quantity` | `INT` | NULL | `` | 数量字段。 |
| `afn_listing_exists` | `BIT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `afn_warehouse_quantity` | `INT` | NULL | `` | 数量字段。 |
| `afn_fulfillable_quantity` | `INT` | NULL | `` | 数量字段。 |
| `afn_unsellable_quantity` | `INT` | NULL | `` | 数量字段。 |
| `afn_reserved_quantity` | `INT` | NULL | `` | 数量字段。 |
| `afn_total_quantity` | `INT` | NULL | `` | 数量字段。 |
| `per_unit_volume` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `afn_inbound_working_quantity` | `INT` | NULL | `` | 数量字段。 |
| `afn_inbound_shipped_quantity` | `INT` | NULL | `` | 数量字段。 |
| `afn_inbound_receiving_quantity` | `INT` | NULL | `` | 数量字段。 |
| `afn_researching_quantity` | `INT` | NULL | `` | 数量字段。 |
| `afn_reserved_future_supply` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `afn_future_supply_buyable` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `store` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 业务幂等键 hash，用于 MERGE/upsert。 |

### 4.11 `amazon_inventory_ledger_detail`

- 数据来源：GET_LEDGER_DETAIL_VIEW_DATA
- 表用途：FBA 仓库事件明细、reference、数量、原因。
- 当前索引：`IX_amazon_inventory_ledger_detail_key`(marketplace_id, seller_sku, fnsku, asin, event_type, reference_id)
- 当前行数：`207`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `ledger_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `fnsku` | `NVARCHAR(100)` | NULL | `` | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `seller_sku` | `NVARCHAR(200)` | NULL | `` | 卖家 SKU。 |
| `title` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `event_type` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `reference_id` | `NVARCHAR(300)` | NULL | `` | 源系统或本系统标识字段。 |
| `quantity` | `INT` | NULL | `` | 数量字段。 |
| `fulfillment_center` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `disposition` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `reason` | `NVARCHAR(300)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `country` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `reconciled_quantity` | `INT` | NULL | `` | 数量字段。 |
| `unreconciled_quantity` | `INT` | NULL | `` | 数量字段。 |
| `date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `store` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `source_row_index` | `INT` | NULL | `` | 010/011 migration 新增；raw file 内 1-based 数据行号，用于行级追溯。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 010/011 migration 新增；业务幂等键 hash，用于 MERGE/upsert。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.12 `amazon_inventory_ledger_summary_daily`

- 数据来源：GET_LEDGER_SUMMARY_VIEW_DATA
- 表用途：每日/地点维度仓库库存变动汇总。
- 当前索引：`IX_amazon_inventory_ledger_summary_daily_key`(marketplace_id, seller_sku, fnsku, asin, ledger_date_raw)；`UX_amazon_inventory_ledger_summary_daily_business_key_hash`(business_key_hash, unique filtered)
- 当前行数：`150`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `ledger_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `fnsku` | `NVARCHAR(100)` | NULL | `` | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `seller_sku` | `NVARCHAR(200)` | NULL | `` | 卖家 SKU。 |
| `title` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `disposition` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `starting_warehouse_balance` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `in_transit_between_warehouses` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `receipts` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `customer_shipments` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `customer_returns` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `vendor_returns` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `warehouse_transfer_in_out` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `found` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `lost` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `damaged` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `disposed` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `other_events` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `ending_warehouse_balance` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `unknown_events` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `location` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `store` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `source_row_index` | `INT` | NULL | `` | 010/011 migration 新增；raw file 内 1-based 数据行号，用于行级追溯。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 010/011 migration 新增；业务幂等键 hash，用于 MERGE/upsert。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.13 `amazon_inventory_planning_daily`

- 数据来源：GET_FBA_INVENTORY_PLANNING_DATA / GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT
- 表用途：库龄、售罄率、days of supply、推荐动作。
- 当前索引：`IX_amazon_inventory_planning_daily_key`(marketplace_id, seller_sku, fnsku, asin, snapshot_date_raw)
- 当前行数：`0`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `snapshot_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `seller_sku` | `NVARCHAR(200)` | NULL | `` | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL | `` | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `condition` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `available_quantity` | `INT` | NULL | `` | 数量字段。 |
| `pending_removal_quantity` | `INT` | NULL | `` | 数量字段。 |
| `inv_age_0_to_90_days` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `inv_age_91_to_180_days` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `inv_age_181_to_270_days` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `inv_age_271_to_365_days` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `inv_age_366_to_455_days` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `inv_age_456_plus_days` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `currency` | `NVARCHAR(10)` | NULL | `` | 币种。 |
| `units_shipped_t7` | `INT` | NULL | `` | 数量字段。 |
| `units_shipped_t30` | `INT` | NULL | `` | 数量字段。 |
| `units_shipped_t60` | `INT` | NULL | `` | 数量字段。 |
| `units_shipped_t90` | `INT` | NULL | `` | 数量字段。 |
| `alert` | `NVARCHAR(300)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `your_price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `sales_price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `recommended_action` | `NVARCHAR(500)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `recommended_sales_price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `recommended_sale_duration_days` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `recommended_removal_quantity` | `INT` | NULL | `` | 数量字段。 |
| `estimated_cost_savings_of_recommended_actions` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `sell_through` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `item_volume` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `volume_unit_measurement` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `storage_type` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `storage_volume` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `marketplace_name` | `NVARCHAR(200)` | NULL | `` | 名称/标题字段。 |
| `product_group` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `sales_rank` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `days_of_supply` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `estimated_excess_quantity` | `INT` | NULL | `` | 数量字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.14 `amazon_listing_snapshot`

- 数据来源：GET_MERCHANT_LISTINGS_ALL_DATA
- 表用途：SKU/ASIN/listing 状态、标题、价格、履约渠道。
- 当前索引：`IX_amazon_listing_snapshot_key`(marketplace_id, snapshot_date DESC, seller_sku, listing_id)；`IX_amazon_listing_snapshot_source`(source_report_id, source_row_hash)；`UX_amazon_listing_snapshot_business_key_hash`(business_key_hash)
- 当前行数：`6`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `snapshot_date` | `DATE` | NOT NULL | `` | 库存/Listing 快照日期。 |
| `listing_id` | `NVARCHAR(200)` | NOT NULL | `` | 源系统或本系统标识字段。 |
| `seller_sku` | `NVARCHAR(200)` | NOT NULL | `` | 卖家 SKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `product_id` | `NVARCHAR(100)` | NULL | `` | 源系统或本系统标识字段。 |
| `product_id_type` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `item_name` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `item_description` | `NVARCHAR(MAX)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `currency` | `NVARCHAR(10)` | NULL | `` | 币种。 |
| `quantity` | `INT` | NULL | `` | 数量字段。 |
| `pending_quantity` | `INT` | NULL | `` | 数量字段。 |
| `open_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `open_date_utc` | `DATETIME2(7)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `item_is_marketplace` | `BIT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `item_condition` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `fulfillment_channel` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `merchant_shipping_group` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `status` | `NVARCHAR(50)` | NULL | `` | 状态字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 业务幂等键 hash，用于 MERGE/upsert。 |

### 4.15 `amazon_marketplace`

- 数据来源：手工 seed / Amazon marketplace metadata
- 表用途：市场、币种、SP-API endpoint。
- 当前索引：`UX_amazon_marketplace_marketplace_id`(marketplace_id)
- 当前行数：`1`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `marketplace_name` | `NVARCHAR(200)` | NOT NULL | `` | 名称/标题字段。 |
| `country_code` | `NVARCHAR(10)` | NOT NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `currency` | `NVARCHAR(10)` | NOT NULL | `` | 币种。 |
| `region` | `NVARCHAR(20)` | NOT NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `endpoint` | `NVARCHAR(300)` | NOT NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `is_active` | `BIT` | NOT NULL | `((1))` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.16 `amazon_order_item`

- 数据来源：GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL
- 表用途：订单/SKU 行、金额、税、促销、发货地区。
- 当前索引：`IX_amazon_order_item_order_sku`(marketplace_id, amazon_order_id, seller_sku, asin)；`IX_amazon_order_item_source`(source_report_id, source_row_hash)；`UX_amazon_order_item_business_key_hash`(business_key_hash, filtered unique)
- 当前行数：`112`
- 当前状态：`007_add_order_item_business_key.sql` 已执行并导出 `after_007_order_item_business_key` live schema；Orders 专用 ingestion 已完成 dry-run、首次 execute 和第二次 execute 幂等性验证。

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `amazon_order_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `merchant_order_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `purchase_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `last_updated_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `order_status` | `NVARCHAR(100)` | NULL | `` | 状态字段。 |
| `fulfillment_channel` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `sales_channel` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `order_channel` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `ship_service_level` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `product_name` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `seller_sku` | `NVARCHAR(200)` | NULL | `` | 卖家 SKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `item_status` | `NVARCHAR(100)` | NULL | `` | 状态字段。 |
| `quantity` | `INT` | NULL | `` | 数量字段。 |
| `currency` | `NVARCHAR(10)` | NULL | `` | 币种。 |
| `item_price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `item_tax` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `shipping_price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `shipping_tax` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `gift_wrap_price` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `gift_wrap_tax` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `item_promotion_discount` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `ship_promotion_discount` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `ship_city` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `ship_state` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `ship_postal_code` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `ship_country` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `promotion_ids` | `NVARCHAR(1000)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `is_business_order` | `BIT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `purchase_order_number` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `price_designation` | `NVARCHAR(100)` | NULL | `` | 金额字段。 |
| `signature_confirmation_recommended` | `BIT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |
| `source_row_index` | `INT` | NULL | `` | raw file 内 1-based 数据行号，用于行级追溯。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | Orders MERGE/upsert 幂等键 hash。 |

### 4.17 `amazon_promotion_performance`

- 数据来源：GET_PROMOTION_PERFORMANCE_REPORT
- 表用途：活动总体浏览、销量、销售额、状态与时间。
- 当前索引：`IX_amazon_promotion_performance_key`(marketplace_id, promotion_id, status)；`UX_amazon_promotion_performance_business_key_hash`(business_key_hash, unique filtered)
- 当前行数：`1`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `promotion_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `merchant_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `promotion_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `promotion_type` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `status` | `NVARCHAR(100)` | NULL | `` | 状态字段。 |
| `glance_views` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `units_sold` | `INT` | NULL | `` | 数量字段。 |
| `revenue` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `revenue_currency_code` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `start_date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `end_date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `created_date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `last_updated_date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `source_row_index` | `INT` | NULL | `` | 010/011 migration 新增；raw file 内 1-based 数据行号，用于行级追溯。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 010/011 migration 新增；业务幂等键 hash，用于 MERGE/upsert。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.18 `amazon_promotion_product_performance`

- 数据来源：GET_PROMOTION_PERFORMANCE_REPORT.productPerformance
- 表用途：活动 ASIN 维度表现。
- 当前索引：`IX_amazon_promotion_product_performance_key`(marketplace_id, promotion_id, asin)；`UX_amazon_promotion_product_performance_business_key_hash`(business_key_hash, unique filtered)
- 当前行数：`3`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `promotion_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `merchant_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `promotion_name` | `NVARCHAR(500)` | NULL | `` | 名称/标题字段。 |
| `promotion_type` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `status` | `NVARCHAR(100)` | NULL | `` | 状态字段。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `product_glance_views` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `product_units_sold` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `product_revenue` | `DECIMAL(18,4)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `product_revenue_currency_code` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `source_row_index` | `INT` | NULL | `` | 010/011 migration 新增；raw file 内 1-based 数据行号，用于行级追溯。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 010/011 migration 新增；业务幂等键 hash，用于 MERGE/upsert。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.19 `amazon_raw_report_file`

- 数据来源：所有 Amazon SP-API / Ads raw files
- 表用途：原始文件路径、hash、行列数、编码、下载时间。
- 当前索引：`IX_amazon_raw_report_file_report`(source_system, report_type, marketplace_id, downloaded_at DESC)；`IX_amazon_raw_report_file_sha256`(sha256)；`UX_amazon_raw_report_file_path`(storage_backend, file_path)
- 当前行数：`0`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `report_request_id` | `BIGINT` | NULL | `` | 源系统或本系统标识字段。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `report_type` | `NVARCHAR(120)` | NOT NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `report_id` | `NVARCHAR(120)` | NULL | `` | 源系统或本系统标识字段。 |
| `report_document_id` | `NVARCHAR(120)` | NULL | `` | 源系统或本系统标识字段。 |
| `file_role` | `NVARCHAR(50)` | NOT NULL | `('raw')` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `storage_backend` | `NVARCHAR(50)` | NOT NULL | `('local')` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `file_path` | `NVARCHAR(700)` | NOT NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `file_name` | `NVARCHAR(300)` | NOT NULL | `` | 名称/标题字段。 |
| `file_extension` | `NVARCHAR(30)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `content_type` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `compression_algorithm` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `encoding` | `NVARCHAR(80)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `delimiter` | `NVARCHAR(20)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `row_count` | `INT` | NULL | `` | 数量字段。 |
| `column_count` | `INT` | NULL | `` | 数量字段。 |
| `sha256` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `byte_size` | `BIGINT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `downloaded_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 时间字段。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.20 `amazon_report_field_catalog`

- 数据来源：字段取样/分析脚本
- 表用途：观察到的源字段、目标表/字段建议、样例值。
- 当前索引：`IX_amazon_report_field_catalog_report`(source_system, report_type, marketplace_id, field_position)
- 当前行数：`0`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `report_type` | `NVARCHAR(120)` | NOT NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `sample_file_id` | `BIGINT` | NULL | `` | 源系统或本系统标识字段。 |
| `field_position` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_field_name` | `NVARCHAR(300)` | NOT NULL | `` | 名称/标题字段。 |
| `normalized_field_name` | `NVARCHAR(200)` | NULL | `` | 名称/标题字段。 |
| `target_table` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `target_column` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `data_type_suggestion` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `nullable_observed` | `BIT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `sample_values_json` | `NVARCHAR(MAX)` | NULL | `` | JSON 结构化内容。 |
| `field_status` | `NVARCHAR(50)` | NOT NULL | `('observed')` | 状态字段。 |
| `notes` | `NVARCHAR(MAX)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.21 `amazon_report_request`

- 数据来源：SP-API Reports createReport/getReports
- 表用途：报告请求、状态、document id、下载/解析状态。
- 当前索引：`IX_amazon_report_request_status`(processing_status, download_status, parse_status, requested_at DESC)；`IX_amazon_report_request_type_range`(source_system, report_type, marketplace_id, data_start_time, data_end_time)；`UX_amazon_report_request_report_id`(marketplace_id, source_system, report_type, report_id)
- 当前行数：`0`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `report_type` | `NVARCHAR(120)` | NOT NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `report_options_json` | `NVARCHAR(MAX)` | NULL | `` | JSON 结构化内容。 |
| `data_start_time` | `DATETIME2(7)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `data_end_time` | `DATETIME2(7)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `report_id` | `NVARCHAR(120)` | NULL | `` | 源系统或本系统标识字段。 |
| `report_document_id` | `NVARCHAR(120)` | NULL | `` | 源系统或本系统标识字段。 |
| `processing_status` | `NVARCHAR(50)` | NOT NULL | `('SUBMITTED')` | 状态字段。 |
| `download_status` | `NVARCHAR(50)` | NOT NULL | `('PENDING')` | 状态字段。 |
| `parse_status` | `NVARCHAR(50)` | NOT NULL | `('PENDING')` | 状态字段。 |
| `requested_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 时间字段。 |
| `last_checked_at` | `DATETIME2(7)` | NULL | `` | 时间字段。 |
| `completed_at` | `DATETIME2(7)` | NULL | `` | 时间字段。 |
| `downloaded_at` | `DATETIME2(7)` | NULL | `` | 时间字段。 |
| `parsed_at` | `DATETIME2(7)` | NULL | `` | 时间字段。 |
| `retry_count` | `INT` | NOT NULL | `((0))` | 数量字段。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `error_message` | `NVARCHAR(MAX)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.22 `amazon_reserved_inventory_daily`

- 数据来源：GET_RESERVED_INVENTORY_DATA
- 表用途：预留数量按 customer orders / FC transfer / processing 拆分。
- 当前索引：`IX_amazon_reserved_inventory_daily_key`(marketplace_id, snapshot_date DESC, seller_sku, fnsku, asin)
- 当前行数：`0`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `snapshot_date` | `DATE` | NOT NULL | `(CONVERT([date],sysutcdatetime()))` | 库存/Listing 快照日期。 |
| `seller_sku` | `NVARCHAR(200)` | NULL | `` | 卖家 SKU。 |
| `fnsku` | `NVARCHAR(100)` | NULL | `` | FBA FNSKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `product_name` | `NVARCHAR(1000)` | NULL | `` | 名称/标题字段。 |
| `reserved_quantity` | `INT` | NULL | `` | 数量字段。 |
| `reserved_customer_orders` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `reserved_fc_transfers` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `reserved_fc_processing` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `program` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.23 `amazon_sales_traffic_asin_daily`

- 数据来源：GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByAsin
- 表用途：ASIN 维度销售、流量、转化率。
- 当前索引：`IX_amazon_sales_traffic_asin_daily_key`(marketplace_id, report_start_date DESC, report_end_date DESC, parent_asin, child_asin)；`IX_amazon_sales_traffic_asin_daily_source`(source_report_id, source_row_hash)；`UX_amazon_sales_traffic_asin_daily_business_key_hash`(business_key_hash, unique filtered)
- 当前行数：`1`
- 当前状态：schema 与真实 execute 已验证；第二次 execute 幂等性通过。

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_start_date` | `DATE` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `report_end_date` | `DATE` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `parent_asin` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `child_asin` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `date_granularity` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `asin_granularity` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `ordered_product_sales_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `ordered_product_sales_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `ordered_product_sales_b2b_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `ordered_product_sales_b2b_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `units_ordered` | `INT` | NULL | `` | 数量字段。 |
| `units_ordered_b2b` | `INT` | NULL | `` | 数量字段。 |
| `total_order_items` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `total_order_items_b2b` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `browser_page_views` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `browser_page_views_b2b` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `browser_page_views_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `browser_page_views_percentage_b2b` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_page_views` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_page_views_b2b` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_page_views_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_page_views_percentage_b2b` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `page_views` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `page_views_b2b` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `page_views_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `page_views_percentage_b2b` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `browser_sessions` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `browser_sessions_b2b` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `browser_session_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `browser_session_percentage_b2b` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_sessions` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_sessions_b2b` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_session_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_session_percentage_b2b` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `sessions` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `sessions_b2b` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `session_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `session_percentage_b2b` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `buy_box_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `buy_box_percentage_b2b` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `unit_session_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `unit_session_percentage_b2b` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 005 migration 新增的稳定业务幂等键；repository 写入时必须非空。 |

### 4.24 `amazon_sales_traffic_daily`

- 数据来源：GET_SALES_AND_TRAFFIC_REPORT.salesAndTrafficByDate
- 表用途：日期维度销售额、订单、退款、sessions、page views、转化率。
- 当前索引：`IX_amazon_sales_traffic_daily_date`(marketplace_id, report_date DESC)；`IX_amazon_sales_traffic_daily_source`(source_report_id, source_row_hash)；`UX_amazon_sales_traffic_daily_business_key_hash`(business_key_hash, unique filtered)
- 当前行数：`6`
- 当前状态：schema 与真实 execute 已验证；第二次 execute 幂等性通过。

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_date` | `DATE` | NOT NULL | `` | 报表日期。 |
| `date_granularity` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `asin_granularity` | `NVARCHAR(50)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `ordered_product_sales_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `ordered_product_sales_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `ordered_product_sales_b2b_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `ordered_product_sales_b2b_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `average_sales_per_order_item_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `average_sales_per_order_item_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `average_sales_per_order_item_b2b_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `average_sales_per_order_item_b2b_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `average_units_per_order_item` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `average_units_per_order_item_b2b` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `average_selling_price_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `average_selling_price_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段。 |
| `average_selling_price_b2b_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `average_selling_price_b2b_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段。 |
| `units_ordered` | `INT` | NULL | `` | 数量字段。 |
| `units_ordered_b2b` | `INT` | NULL | `` | 数量字段。 |
| `total_order_items` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `total_order_items_b2b` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `units_refunded` | `INT` | NULL | `` | 数量字段。 |
| `refund_rate` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `claims_granted` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `claims_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `claims_amount_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段。 |
| `shipped_product_sales_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `shipped_product_sales_currency` | `NVARCHAR(10)` | NULL | `` | 金额字段对应币种。 |
| `units_shipped` | `INT` | NULL | `` | 数量字段。 |
| `orders_shipped` | `INT` | NULL | `` | 数量字段。 |
| `browser_page_views` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_page_views` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `page_views` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `browser_sessions` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `mobile_app_sessions` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `sessions` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `buy_box_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `order_item_session_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `unit_session_percentage` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `average_offer_count` | `DECIMAL(18,6)` | NULL | `` | 数量字段。 |
| `average_parent_items` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `feedback_received` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `negative_feedback_received` | `INT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `received_negative_feedback_rate` | `DECIMAL(18,6)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 005 migration 新增的稳定业务幂等键；repository 写入时必须非空。 |

### 4.25 `amazon_schema_validation_event`

- 数据来源：下载后/入库前 schema validation
- 表用途：字段漂移、缺字段、新字段、requires_review 和通知状态。
- 当前索引：`IX_amazon_schema_validation_event_report`(source_system, report_type, marketplace_id, created_at DESC)；`IX_amazon_schema_validation_event_review`(requires_review, notification_status, created_at DESC)
- 当前行数：`44`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `report_type` | `NVARCHAR(120)` | NOT NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `report_id` | `NVARCHAR(120)` | NULL | `` | 源系统或本系统标识字段。 |
| `raw_file_id` | `BIGINT` | NULL | `` | 源系统或本系统标识字段。 |
| `raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `validation_stage` | `NVARCHAR(80)` | NOT NULL | `('post_download')` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `validation_status` | `NVARCHAR(80)` | NOT NULL | `` | 状态字段。 |
| `severity` | `NVARCHAR(50)` | NOT NULL | `('info')` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `row_count` | `INT` | NULL | `` | 数量字段。 |
| `observed_fields_json` | `NVARCHAR(MAX)` | NULL | `` | JSON 结构化内容。 |
| `expected_fields_json` | `NVARCHAR(MAX)` | NULL | `` | JSON 结构化内容。 |
| `missing_fields_json` | `NVARCHAR(MAX)` | NULL | `` | JSON 结构化内容。 |
| `new_fields_json` | `NVARCHAR(MAX)` | NULL | `` | JSON 结构化内容。 |
| `unmapped_fields_json` | `NVARCHAR(MAX)` | NULL | `` | JSON 结构化内容。 |
| `requires_review` | `BIT` | NOT NULL | `((0))` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `notification_status` | `NVARCHAR(50)` | NOT NULL | `('not_required')` | 状态字段。 |
| `notified_at` | `DATETIME2(7)` | NULL | `` | 时间字段。 |
| `message` | `NVARCHAR(MAX)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |

### 4.26 `amazon_settlement_transaction`

- 数据来源：GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2
- 表用途：实际入账财务明细、费用、退款、广告扣费、Coupon/Deal 费用、分类字段。
- 当前索引：`IX_amazon_settlement_transaction_order_sku`(marketplace_id, order_id, seller_sku, amount_category, profit_bucket)；`IX_amazon_settlement_transaction_settlement`(marketplace_id, settlement_id, is_settlement_summary, transaction_type)；`IX_amazon_settlement_transaction_source`(source_report_id, source_row_hash)；`UX_amazon_settlement_transaction_business_key_hash`(business_key_hash, filtered unique)
- 当前行数：`4911`
- 行数说明：用户本地已完成 Settlement 首次 execute inserted=4911 和第二次 execute updated=4911；下次 schema export 可刷新 runtime snapshot 中的 row count。

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `settlement_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `settlement_start_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `settlement_end_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `deposit_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `total_amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `currency` | `NVARCHAR(10)` | NULL | `` | 币种。 |
| `is_settlement_summary` | `BIT` | NOT NULL | `((0))` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `transaction_type` | `NVARCHAR(120)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `order_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `merchant_order_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `adjustment_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `shipment_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `marketplace_name` | `NVARCHAR(200)` | NULL | `` | 名称/标题字段。 |
| `amount_type` | `NVARCHAR(120)` | NULL | `` | 金额字段。 |
| `amount_description` | `NVARCHAR(300)` | NULL | `` | 金额字段。 |
| `amount` | `DECIMAL(18,4)` | NULL | `` | 金额字段。 |
| `amount_category` | `NVARCHAR(120)` | NOT NULL | `` | 金额字段。 |
| `profit_bucket` | `NVARCHAR(120)` | NOT NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `fulfillment_id` | `NVARCHAR(100)` | NULL | `` | 源系统或本系统标识字段。 |
| `posted_date_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `posted_date_time_raw` | `NVARCHAR(100)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `order_item_code` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `merchant_order_item_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `merchant_adjustment_item_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `seller_sku` | `NVARCHAR(200)` | NULL | `` | 卖家 SKU。 |
| `quantity_purchased` | `INT` | NULL | `` | 数量字段。 |
| `promotion_id` | `NVARCHAR(500)` | NULL | `` | 源系统或本系统标识字段。 |
| `source_system` | `NVARCHAR(50)` | NOT NULL | `('sp_api_reports')` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `source_report_type` | `NVARCHAR(120)` | NOT NULL | `` | Amazon reportType/reportTypeId。 |
| `source_report_id` | `NVARCHAR(120)` | NULL | `` | Amazon report id / Ads report id。 |
| `source_report_request_id` | `BIGINT` | NULL | `` | 本系统 report request 控制表 id。 |
| `source_raw_file_id` | `BIGINT` | NULL | `` | 本系统 raw file 归档表 id；当前部分入库链路仍为 NULL，后续应补强关联。 |
| `source_raw_file_path` | `NVARCHAR(1000)` | NULL | `` | 本地或云端 raw file 路径。 |
| `source_run_id` | `BIGINT` | NULL | `` | 对应 amazon_sync_run_log.id。 |
| `source_row_hash` | `NVARCHAR(100)` | NOT NULL | `` | 原始行 hash，用于追溯，不作为业务 upsert 主键。 |
| `raw_data` | `NVARCHAR(MAX)` | NOT NULL | `` | 保留原始行 JSON，便于重放和排查。 |
| `source_row_index` | `INT` | NULL | `` | 006 新增；源文件内数据行序号，用于稳定定位 settlement row。 |
| `business_key_hash` | `NVARCHAR(100)` | NULL | `` | 006 新增；业务幂等键 hash，用于 Settlement MERGE/upsert。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.27 `amazon_sku_cost`

- 数据来源：手工维护/会计成本输入
- 表用途：SKU 采购、头程、包装等单位成本。
- 当前索引：`IX_amazon_sku_cost_effective`(marketplace_id, seller_sku, effective_from, effective_to)
- 当前行数：`0`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `marketplace_id` | `NVARCHAR(50)` | NOT NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `seller_sku` | `NVARCHAR(200)` | NOT NULL | `` | 卖家 SKU。 |
| `asin` | `NVARCHAR(50)` | NULL | `` | Amazon ASIN。 |
| `product_cost` | `DECIMAL(18,4)` | NOT NULL | `((0))` | 单件商品采购/货款成本；利润核算 v1.0 成本组成之一。 |
| `first_mile_cost` | `DECIMAL(18,4)` | NOT NULL | `((0))` | 单件头程、海运、清关、入仓等分摊成本；利润核算 v1.0 成本组成之一。 |
| `packaging_cost` | `DECIMAL(18,4)` | NOT NULL | `((0))` | 单件包装、吊牌、说明书等可归属包装成本；利润核算 v1.0 成本组成之一。 |
| `other_unit_cost` | `DECIMAL(18,4)` | NOT NULL | `((0))` | 其他可稳定归属到单件 SKU 的成本；利润核算 v1.0 成本组成之一。 |
| `currency` | `NVARCHAR(10)` | NOT NULL | `` | 币种。 |
| `effective_from` | `DATE` | NOT NULL | `` | 成本生效开始日期；第一版按 Settlement posted date 匹配成本区间。 |
| `effective_to` | `DATE` | NULL | `` | 成本生效结束日期；NULL 表示持续有效。 |
| `remark` | `NVARCHAR(MAX)` | NULL | `` | 成本来源、换算说明、批次或人工备注。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

### 4.28 `amazon_sync_run_log`

- 数据来源：所有采集/解析/入库任务
- 表用途：任务运行状态、行数、耗时、错误信息。
- 当前索引：`IX_amazon_sync_run_log_job_started`(job_name, started_at DESC)；`IX_amazon_sync_run_log_status_started`(status, started_at DESC)；`IX_amazon_sync_run_log_workflow_started`(workflow_name, started_at DESC)
- 当前行数：`20`

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `workflow_name` | `NVARCHAR(120)` | NULL | `` | 名称/标题字段。 |
| `job_name` | `NVARCHAR(120)` | NOT NULL | `` | 名称/标题字段。 |
| `task_type` | `NVARCHAR(80)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `trigger_type` | `NVARCHAR(50)` | NOT NULL | `('manual')` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `run_mode` | `NVARCHAR(50)` | NOT NULL | `('local')` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `parent_run_id` | `BIGINT` | NULL | `` | 源系统或本系统标识字段。 |
| `job_execution_id` | `NVARCHAR(200)` | NULL | `` | 源系统或本系统标识字段。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 ATVPDKIKX0DER。 |
| `source_system` | `NVARCHAR(50)` | NULL | `` | 数据来源系统，通常为 sp_api_reports 或 amazon_ads。 |
| `status` | `NVARCHAR(50)` | NOT NULL | `('running')` | 状态字段。 |
| `started_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 时间字段。 |
| `finished_at` | `DATETIME2(7)` | NULL | `` | 时间字段。 |
| `duration_ms` | `BIGINT` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `date_start` | `DATE` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `date_end` | `DATE` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `rows_read` | `INT` | NOT NULL | `((0))` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `rows_written` | `INT` | NOT NULL | `((0))` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `rows_skipped` | `INT` | NOT NULL | `((0))` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `rows_failed` | `INT` | NOT NULL | `((0))` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `files_created` | `INT` | NOT NULL | `((0))` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `retry_count` | `INT` | NOT NULL | `((0))` | 数量字段。 |
| `config_snapshot_json` | `NVARCHAR(MAX)` | NULL | `` | JSON 结构化内容。 |
| `message` | `NVARCHAR(MAX)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `error_type` | `NVARCHAR(200)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `error_detail` | `NVARCHAR(MAX)` | NULL | `` | 按源报告字段语义保存；后续可在功能文档中继续细化。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |

### 4.29 `pipeline_job_config`

- 数据来源：手动 seed / 未来自动化任务配置
- 表用途：记录数据下载、入库、加工、报表和邮件任务的默认参数、执行周期、回看窗口和执行阶段。
- 当前索引：`UX_pipeline_job_config_job_key`(job_key, unique)；`IX_pipeline_job_config_enabled_phase`(enabled, execution_phase, job_group, manual_run_order)；`IX_pipeline_job_config_marketplace_domain`(marketplace_id, data_domain, job_group)
- 当前行数：`13`
- 当前说明：第一批 seed 包含 10 个核心 ingestion 任务，以及 Profit、Weekly Report、Email 三个 placeholder；placeholder 当前 `enabled=0`，待对应功能实现后再启用。

| 字段 | 类型 | 可空 | 默认值 | 字段说明 |
|---|---|---|---|---|
| `id` | `BIGINT` | NOT NULL | `` | 数据库自增主键。 |
| `job_key` | `NVARCHAR(160)` | NOT NULL | `` | 稳定唯一任务键，例如 `manual.ingest.inventory_snapshot.us`。 |
| `job_group` | `NVARCHAR(40)` | NOT NULL | `` | 任务分组：`download` / `ingest` / `process` / `report` / `email`。 |
| `job_name` | `NVARCHAR(240)` | NOT NULL | `` | 人类可读任务名称。 |
| `source_system` | `NVARCHAR(50)` | NULL | `` | 数据来源系统，例如 `sp_api_reports`、`amazon_ads`、`internal`、`email`。 |
| `marketplace_id` | `NVARCHAR(50)` | NULL | `` | Amazon marketplace id，例如 `ATVPDKIKX0DER`。 |
| `profile_id` | `NVARCHAR(100)` | NULL | `` | Amazon Ads profile id；非 Ads 任务可为空。 |
| `data_domain` | `NVARCHAR(80)` | NOT NULL | `` | 业务数据域，例如 `inventory_snapshot`、`settlement`、`profit_calculation`。 |
| `report_type` | `NVARCHAR(180)` | NULL | `` | SP-API report type 或 Ads report group；内部加工任务可为空。 |
| `target_table` | `NVARCHAR(300)` | NULL | `` | 主要目标表；多表任务使用分号分隔；内部报表任务可为空。 |
| `script_path` | `NVARCHAR(500)` | NOT NULL | `` | 当前手动或未来自动化调用的脚本路径。 |
| `default_args_json` | `NVARCHAR(MAX)` | NULL | `` | 默认 CLI 参数 JSON，受 `ISJSON` check constraint 约束。 |
| `manual_run_order` | `INT` | NULL | `` | 手动 checklist 建议执行顺序。 |
| `recommended_cadence_unit` | `NVARCHAR(20)` | NOT NULL | `` | 建议周期单位：`hour` / `day` / `week` / `month` / `on_demand`。 |
| `recommended_cadence_value` | `INT` | NOT NULL | `((1))` | 建议周期值，例如 1 表示每 1 day/week。 |
| `default_lookback_days` | `INT` | NULL | `` | 默认回看窗口天数。 |
| `data_window_lag_days` | `INT` | NULL | `` | 数据延迟安全窗口天数。 |
| `execution_phase` | `NVARCHAR(40)` | NOT NULL | `('manual_first')` | 执行阶段：`manual_first` / `scheduled_candidate` / `scheduled_active` / `deprecated`。 |
| `enabled` | `BIT` | NOT NULL | `((1))` | 是否启用；未实现的利润、周报、邮件 placeholder 当前应为 0。 |
| `notes` | `NVARCHAR(MAX)` | NULL | `` | 业务说明和限制。 |
| `created_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录创建时间 UTC。 |
| `updated_at` | `DATETIME2(7)` | NOT NULL | `(sysutcdatetime())` | 数据库记录最后更新时间 UTC。 |

## 6. 当前已准备但尚未执行的 migration

当前无已准备但未执行的 migration。后续新增结构变更从 `013_xxx.sql` 开始。
