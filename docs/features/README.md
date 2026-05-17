# 功能设计文档索引

> 更新时间：2026-05-17  
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
| [`feature_inventory_ledger_ingestion.md`](feature_inventory_ledger_ingestion.md) | Implementing | SP-API Inventory Ledger summary/detail -> 2 张库存流水表；011 已执行，专用 dry-run/schema guard/repository/CLI 已开发并通过 dry-run，待 execute/幂等验证。 |

## 3. 下一批建议

按当前项目进度，后续应优先：

1. 用户本地执行 `scripts/ingest_inventory_ledger_reports.py` dry-run / execute / 第二次 execute，完成 Inventory Ledger 幂等性验收。
2. 通过后将 Inventory Ledger 更新为 `Implemented`。
3. 两组运营/库存补充数据完成后，进入 `feature_profit_calculation.md`。
4. 利润核算稳定后，再做 `feature_weekly_operations_report.md` 和 `feature_clearance_decision_support.md`。

`feature_listing_snapshot_ingestion.md`、`feature_inventory_ingestion.md`、`feature_sales_traffic_ingestion.md`、`feature_settlement_ingestion.md`、`feature_orders_ingestion.md`、`feature_fba_reimbursements_ingestion.md`、`feature_fba_fee_preview_ingestion.md` 和 `feature_promotion_coupon_ingestion.md` 均已完成当前阶段设计与实现；对应 `003`-`010` migration 已执行成功并同步到 current schema spec。八条 SP-API normalized ingestion 链路已经完成 dry-run、schema guard、repository/upsert、CLI、首次 execute 和第二次 execute 幂等性验证：Listing、Inventory、Sales & Traffic、Settlement、Orders、FBA Reimbursements、FBA Fee Preview、Promotion/Coupon。
