# SellerDataPipeline 文档总索引

> 更新时间：2026-05-17  
> 文档定位：本目录是 SellerDataPipeline 的正式文档入口。未来新需求、新设计、新数据库变更和开发进度都应优先维护在 `docs/` 下。`requirements/` 中历史文档只作为迁移来源或兼容参考。

## 1. 文档体系目标

本项目后续会大量依赖 AI 辅助迭代，因此文档体系需要做到：

1. 需求、设计、实现状态分离，避免混在同一个文档里。
2. 数据接入能力和业务功能设计分离，避免“能拿到什么数据”和“拿来做什么功能”混淆。
3. 数据库设计意图和当前真实数据库状态分离，避免误把未来设计当成已执行事实。
4. 每次开发都有可追溯的功能文档、migration 和进度记录。
5. AI 接手时能快速判断哪些内容是事实，哪些内容是计划，哪些内容已弃置。

## 2. 目录结构

```text
docs/
  README.md

  project/
    project_overview.md           # 项目目的、边界、架构与阶段
    development_rules.md          # 开发、文档、测试、数据库维护规则
    iteration_workflow.md          # 新需求 -> 设计 -> migration -> 开发 -> 验收 -> 文档同步 SOP
    progress_next_steps.md        # 当前真实进度和下一步计划

  data_access/
    README.md
    amazon_data_access_catalog.md
    sp_api_reports_catalog.md
    amazon_ads_reports_catalog.md
    seller_central_manual_exports.md

  features/
    README.md                     # 功能文档索引
    FEATURE_TEMPLATE.md           # 单功能设计文档标准模板
    feature_azure_sql_foundation.md
    feature_ads_ingestion.md
    feature_listing_snapshot_ingestion.md
    # feature_weekly_operations_report.md

  database/
    database_current_schema_spec.md
    database_migration_policy.md
    database_schema_export_tool.md
    azure_sql_connection_runbook.md
    # database_field_naming_conventions.md # 后续需要时补充

  adr/
    ADR-001-documentation-structure.md
    ADR-002-do-not-edit-executed-migrations.md
    ADR-003-feature-doc-before-implementation.md
    ADR-004-database-spec-from-live-schema.md
    ADR-005-progressive-generalization.md
    ADR-006-azure-sql-connection-warmup.md
```

## 3. 文档职责边界

| 文档类别 | 回答的问题 | 不应该写什么 |
|---|---|---|
| `project/` | 项目是什么、当前在哪一步、开发规则是什么 | 不写具体字段映射和长篇源数据结构 |
| `data_access/` | Amazon / Ads / Seller Central 能拿到什么数据、如何获取、样例结构和源字段 | 不写利润计算、周报口径、业务功能实现 |
| `features/` | 某个具体功能如何设计、如何实现、如何验收 | 不替代当前真实数据库 spec |
| `database/` | 当前数据库真实结构、migration 规则、真实 schema 导出工具 | 不写未执行的未来表结构为事实 |
| `adr/` | 为什么做出某个长期架构决策 | 不写临时 TODO 或日常进度 |

## 4. 推荐阅读顺序

新 AI 或新开发者接手时，按以下顺序阅读：

1. 根目录 [`README.md`](../README.md)
2. [`project/project_overview.md`](project/project_overview.md)
3. [`project/development_rules.md`](project/development_rules.md)
4. [`project/iteration_workflow.md`](project/iteration_workflow.md)
5. [`project/progress_next_steps.md`](project/progress_next_steps.md)
6. [`data_access/amazon_data_access_catalog.md`](data_access/amazon_data_access_catalog.md)
7. [`database/database_migration_policy.md`](database/database_migration_policy.md)
8. [`database/database_schema_export_tool.md`](database/database_schema_export_tool.md)
9. [`database/azure_sql_connection_runbook.md`](database/azure_sql_connection_runbook.md)
10. [`database/database_current_schema_spec.md`](database/database_current_schema_spec.md)
11. [`features/README.md`](features/README.md)
12. 已实现功能：[`features/feature_azure_sql_foundation.md`](features/feature_azure_sql_foundation.md)、[`features/feature_ads_ingestion.md`](features/feature_ads_ingestion.md)
13. 已实现功能：[`features/feature_listing_snapshot_ingestion.md`](features/feature_listing_snapshot_ingestion.md)；对应 003 migration 已执行，Listing dry-run / repository / CLI / execute / 幂等性已完成
14. 已实现功能：[`features/feature_inventory_ingestion.md`](features/feature_inventory_ingestion.md)；对应 004 migration 已执行，Inventory dry-run / repository / CLI / execute / 幂等性已完成
15. 已实现功能：[`features/feature_sales_traffic_ingestion.md`](features/feature_sales_traffic_ingestion.md)，005 migration、专用 ingestion、真实 execute 和幂等性验证均已完成
16. 已实现功能：[`features/feature_settlement_ingestion.md`](features/feature_settlement_ingestion.md)，006 已执行，Settlement 专用 dry-run / repository / CLI / execute / 幂等性已完成
17. 已实现功能：[`features/feature_orders_ingestion.md`](features/feature_orders_ingestion.md)，Orders 007 已执行，专用 ingestion、真实 execute 和幂等性验证均已完成
18. 已实现功能：[`features/feature_fba_reimbursements_ingestion.md`](features/feature_fba_reimbursements_ingestion.md)，`008` 已执行，dry-run / execute / 幂等性验证已完成
19. 当前功能：[`features/feature_fba_fee_preview_ingestion.md`](features/feature_fba_fee_preview_ingestion.md)，009 已执行，专用 dry-run 已完成，已完成 execute/幂等验证
19. 相关 ADR，尤其 `ADR-005-progressive-generalization.md` 与 `ADR-006-azure-sql-connection-warmup.md`

## 5. 当前迁移与治理进展

当前第一批已建立文档体系、规则、进度和数据库当前 spec；第二批已建立数据接入目录。后续应继续分批迁移和完善：

1. `data_access/` 数据接入目录已建立：SP-API、Amazon Ads、Seller Central 手动导出已拆分。
2. 已实现功能文档已建立：`feature_azure_sql_foundation.md` 和 `feature_ads_ingestion.md`。
3. 已实现功能文档已建立并验收：`feature_listing_snapshot_ingestion.md` 和 `feature_inventory_ingestion.md`。
4. Listing 第一项 schema 变更 migration 已执行：`sql/migrations/003_add_listing_snapshot_business_key_hash.sql`；current schema spec 已同步。
5. 迭代 SOP 已建立：`project/iteration_workflow.md`；要求新需求先分类、先更新设计文档、数据库变更后从真实 Azure SQL 读取 schema 再更新 current spec。
6. 新增 ADR：`ADR-003-feature-doc-before-implementation.md` 和 `ADR-004-database-spec-from-live-schema.md`。
7. 新增真实 schema 导出工具文档：`database/database_schema_export_tool.md`；后续 migration 后应优先导出 live schema，再更新 current spec。
8. 新增 Azure SQL 连接故障处理 runbook：`database/azure_sql_connection_runbook.md`，明确区分 idle/resume timeout 与 firewall/IP allowlist 错误。
9. Inventory 的 `004_add_inventory_daily_business_key_hash.sql` 已执行，live schema/current spec 已同步，专用入口/repository/dry-run/execute/幂等性验证已完成。
10. Sales & Traffic 功能文档 `feature_sales_traffic_ingestion.md` 已建立；`005_add_sales_traffic_business_key_hashes.sql` 已执行并同步 spec；专用 ingestion、真实 execute 和幂等性验证已完成。
11. Settlement 功能文档 `feature_settlement_ingestion.md` 已完成验收：`006_add_settlement_transaction_business_key.sql` 已执行，专用 dry-run / repository / CLI / execute / 幂等性验证均已完成。
12. Orders 功能文档 `feature_orders_ingestion.md` 已完成验收：`007_add_order_item_business_key.sql` 已执行，专用 dry-run / repository / CLI / execute / 幂等性验证均已完成。
13. FBA Reimbursements 功能文档 `feature_fba_reimbursements_ingestion.md` 已完成验收：`008_add_fba_reimbursement_business_key.sql` 已执行，专用 dry-run / repository / CLI / execute / 幂等性验证均已完成。
14. FBA Fee Preview 功能已完成 dry-run、execute 和第二次 execute 幂等性验证。
15. Promotion/Coupon 功能已完成 `010`、dry-run、execute 和第二次 execute 幂等性验证。
16. Inventory Ledger 功能已完成 `011`、专用 dry-run/schema guard/repository/CLI，已完成 execute/幂等验证。
15. 后续再补充利润、周报、清仓决策等业务分析功能文档。

## 6. 维护硬规则

1. 新需求提出后，先按 `project/iteration_workflow.md` 分类和确认工作流。
2. 新功能开发前，先创建或更新对应 `features/feature_*.md`。
3. 新数据源接入前，先更新 `data_access/` 下对应 catalog。
4. 涉及数据库结构变化时，先对比 `database_current_schema_spec.md`，再新增 migration。
5. 已执行过的 migration 不允许修改。
6. migration 执行成功后，优先运行 `scripts/export_database_schema_spec.py` 导出真实 Azure SQL schema，再更新 `database_current_schema_spec.md` 和 `progress_next_steps.md`。
7. 真实 SQL 入口必须复用 `get_connection()`，让连接层完成 Azure SQL retry + `SELECT 1` warm-up。
8. firewall/IP allowlist 错误不是 warm-up 问题，不应靠重试解决；按 `database/azure_sql_connection_runbook.md` 放行当前公网 IP 或配置云端固定出站网络。
9. 已弃置的功能不要删除历史，应在功能文档里标记 `Deprecated` 并说明原因。


## Promotion/Coupon 与 Inventory Ledger 补充数据

2026-05-17 已新增两份功能设计并准备对应 migration：

```text
docs/features/feature_promotion_coupon_ingestion.md
sql/migrations/010_add_promotion_coupon_business_keys.sql

docs/features/feature_inventory_ledger_ingestion.md
sql/migrations/011_add_inventory_ledger_business_keys.sql
```

Promotion/Coupon 用于优惠券、折扣、会员日/Prime Day 等活动效果分析，已完成入库验收；Inventory Ledger 用于库存 movement 与库存审计，已完成 execute/幂等验证。周报中的当前库存余额仍优先来自 `amazon_inventory_daily`，Ledger 用于解释库存变化。
