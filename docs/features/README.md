# 功能设计文档索引

> 更新时间：2026-05-16  
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

## 3. 下一批建议补充的功能文档

按当前项目进度，后续应优先补充：

1. `feature_inventory_ingestion.md`
2. `feature_sales_traffic_ingestion.md`
3. `feature_settlement_ingestion.md`
4. `feature_profit_calculation.md`
5. `feature_weekly_operations_report.md`
6. `feature_clearance_decision_support.md`

`feature_listing_snapshot_ingestion.md` 已完成当前阶段设计与实现，且 `sql/migrations/003_add_listing_snapshot_business_key_hash.sql` 已执行成功并同步到 current schema spec。Listing dry-run、schema guard、repository/upsert、CLI、首次 execute 和第二次 execute 幂等性均已完成。下一步应先补 `feature_inventory_ingestion.md`，再进入 Inventory 入库开发。
