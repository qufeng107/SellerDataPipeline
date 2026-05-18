# 功能设计文档索引

> 更新时间：2026-05-18  
> 文档定位：本目录记录 SellerDataPipeline 的单功能设计、实现状态、验收标准和相关代码路径。每个功能文档必须以 `FEATURE_TEMPLATE.md` 为标准，不应把多个功能混在同一份文档里。

## 1. 功能文档维护规则

1. 新功能开发前，先创建或更新对应 `feature_*.md`。
2. 功能文档可以写目标设计，但不能把未执行的数据库结构写成当前事实。
3. 涉及数据库变化时，先在功能文档中说明设计原因，再新增 migration；migration 执行成功后再更新 `docs/database/database_current_schema_spec.md`。
4. 功能完成后，必须更新功能状态、验收证据和 `docs/project/progress_next_steps.md`。
5. 已弃置方案不要删除，应在功能文档的弃置记录中说明原因和替代方案。

## 2. 当前功能文档清单

| 功能文档 | 功能状态 | 说明 |
|---|---|---|
| [`FEATURE_TEMPLATE.md`](FEATURE_TEMPLATE.md) | Template | 单功能设计文档标准模板。 |
| [`feature_azure_sql_foundation.md`](feature_azure_sql_foundation.md) | Implemented | Azure SQL 连接、初始 migration、数据库检查脚本和数据库治理规则。 |
| [`feature_ads_ingestion.md`](feature_ads_ingestion.md) | Implemented | Amazon Ads Sponsored Products 四类日报入库闭环。 |
| [`feature_listing_snapshot_ingestion.md`](feature_listing_snapshot_ingestion.md) | Implemented | SP-API `GET_MERCHANT_LISTINGS_ALL_DATA` -> `amazon_listing_snapshot`；dry-run、schema guard、repository、CLI、真实 Azure SQL execute 和幂等性验证已完成。 |
| [`feature_inventory_ingestion.md`](feature_inventory_ingestion.md) | Implemented | SP-API `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` -> `amazon_inventory_daily`；004、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_sales_traffic_ingestion.md`](feature_sales_traffic_ingestion.md) | Implemented | SP-API `GET_SALES_AND_TRAFFIC_REPORT` -> `amazon_sales_traffic_daily` / `amazon_sales_traffic_asin_daily`；005、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_settlement_ingestion.md`](feature_settlement_ingestion.md) | Implemented | SP-API `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` -> `amazon_settlement_transaction`；006、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_orders_ingestion.md`](feature_orders_ingestion.md) | Implemented | SP-API `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` -> `amazon_order_item`；007、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_fba_reimbursements_ingestion.md`](feature_fba_reimbursements_ingestion.md) | Implemented | SP-API `GET_FBA_REIMBURSEMENTS_DATA` -> `amazon_fba_reimbursement`；008、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_fba_fee_preview_ingestion.md`](feature_fba_fee_preview_ingestion.md) | Implemented | SP-API `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` -> `amazon_fba_fee_preview`；009、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_promotion_coupon_ingestion.md`](feature_promotion_coupon_ingestion.md) | Implemented | SP-API Promotion/Coupon reports -> 4 张促销/优惠券表；010、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_inventory_ledger_ingestion.md`](feature_inventory_ledger_ingestion.md) | Implemented | SP-API Inventory Ledger summary/detail -> 2 张库存流水表；011 已执行，专用 ingestion 已完成 execute/幂等验证。 |
| [`feature_ingestion_job_config.md`](feature_ingestion_job_config.md) | Implemented | 数据下载/入库/加工/报表任务周期配置表；012 migration 和 seed 已执行，`pipeline_job_config` 当前 13 行。 |
| [`feature_profit_calculation.md`](feature_profit_calculation.md) | Planned / policy frozen | 利润核算口径已冻结为 Settlement-led Financial Profit v1.0；第一版以 Settlement 财务主口径 + SKU 标准成本为核心，先生成人工复核文件，不立即新增利润结果表。 |
| [`feature_sku_cost_management.md`](feature_sku_cost_management.md) | Implemented | SKU 成本 xlsx 模板导出与导入；默认 dry-run、按 marketplace + SKU + effective_from 幂等写入 `amazon_sku_cost`。 |

## 3. 下一批建议

当前核心 ingestion 功能已全部完成。后续优先级应切换为：

1. 按 `feature_profit_calculation.md` 开发利润计算 dry-run / preview。
2. 使用 `feature_sku_cost_management.md` 导出/导入 SKU 成本、包装成本、头程/海运成本，并验证缺成本阻塞规则。
3. 先用真实 3月/4月或 5月上旬数据人工复核利润结果。
4. 连续几期稳定后，再判断是否新增利润 fact 表、视图或报表输出表。
5. 利润核算稳定后，再做 `feature_weekly_operations_report.md` 和 `feature_clearance_decision_support.md`。

已完成当前阶段设计与实现的 ingestion 功能包括：Listing、Inventory、Sales & Traffic、Settlement、Orders、FBA Reimbursements、FBA Fee Preview、Promotion/Coupon、Inventory Ledger 和 Ads。对应 migration `003`-`011` 已执行成功；任务周期配置 migration `012` 和 seed 也已执行成功。
