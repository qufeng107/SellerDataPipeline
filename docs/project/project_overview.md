# SellerDataPipeline 项目总览

> 更新时间：2026-05-17  
> 文档定位：说明项目目的、边界、阶段目标、整体架构和当前真实状态。详细进度见 `docs/project/progress_next_steps.md`；数据库真实结构见 `docs/database/database_current_schema_spec.md`。

## 1. 项目背景

SellerDataPipeline 是一个面向小体量跨境电商公司的轻量级 Amazon 运营数据管道项目。公司当前已有美国 Amazon 店铺，短期目标是先把美国站运营数据自动沉淀下来，减少手工导表和人工核算；中长期目标是在合适时机支持更多国际市场和更多自动化运营分析。

项目的核心价值不是单纯“下载报表”，而是建立一套稳定的数据底座：

```text
Amazon raw data
  -> structured Azure SQL data
  -> consistent business metrics
  -> repeatable reports and decisions
```

## 2. 业务目标

第一阶段服务以下业务问题：

1. **利润核算**：把 settlement、订单、广告费、Coupon/Promotion、SKU 成本等统一起来，支持周度、月度利润估算和会计报表准备。
2. **广告优化**：沉淀 Amazon Ads campaign、targeting、search term、advertised product 数据，用于判断 ACOS、ROAS、无效花费、加词和否词。
3. **库存监控**：沉淀 FBA 库存、预留库存、库存流水、补货建议，用于识别断货、滞销、库龄和清仓风险。
4. **Listing 监控**：沉淀 SKU/ASIN/listing 快照，用于追踪商品状态、价格、fulfillment channel、标题等基础信息。
5. **促销复盘**：沉淀 Coupon、Promotion、Deal 相关数据，用于判断促销带来的销量、折扣成本和真实贡献。
6. **周期报表**：后续生成周报、月报、季度报税数据包，减少手工整理。
7. **清仓决策支持**：结合库存、广告、价格、促销和利润数据，为低动销库存提供折扣、广告、清仓建议。

## 3. 技术目标

项目技术形态应保持轻量、可审计、可部署：

- 使用普通 Python 项目，不做 Django / Web 后台。
- 使用 `src/ + scripts/ + tests/` 结构。
- 使用 Azure SQL 作为结构化数据仓库。
- 使用本地 raw file 和后续 Blob Storage 保存原始报表。
- 使用 schema guard 检查字段漂移，避免 Amazon 报表字段变化后静默写错库。
- 使用 repository 层统一数据库 upsert，不在业务代码里到处拼 SQL。
- 使用 dry-run preview 支持入库前人工检查。
- 后续使用 Azure Container Apps Jobs 做定时任务，而不是让 GitHub Actions 充当长期业务调度器。

## 4. 非目标 / 边界

当前阶段明确不做：

1. 不做 Django / Web 管理后台。
2. 不做复杂数据湖或大数据平台。
3. 不在第一阶段做多租户 SaaS。
4. 不把 Excel 当成唯一数据源；Excel 只作为输出和人工复核载体。
5. 不直接用未验证字段做财务结论；财务口径需要分阶段确认。
6. 不在未跑通本地入库闭环前提前上 Azure Container Apps Jobs。

## 5. 整体数据流

```text
Amazon SP-API Reports
Amazon Ads API Reports
Seller Central manual exports
        |
        v
reports/raw/ 或 Azure Blob Storage
        |
        v
parser / analyzer
        |
        v
schema guard / field catalog / validation event
        |
        v
dry-run preview
        |
        v
repository MERGE/upsert
        |
        v
Azure SQL normalized tables
        |
        v
reports / dashboards / decision support / scheduled jobs
```

## 6. 代码分层

```text
scripts/
  命令行入口。原则上只负责参数解析、打印结果、调用业务层。

src/seller_data_pipeline/config/
  环境变量、运行模式、默认配置。

src/seller_data_pipeline/common/
  日志、日期窗口、金额处理、hash、异常、重试等公共能力。

src/seller_data_pipeline/integrations/amazon/
  Amazon SP-API 和 Amazon Ads API 客户端、鉴权、报告请求和下载。

src/seller_data_pipeline/parsers/amazon/
  原始报表解析，把 raw txt/json/csv 转为结构化 Python record。

src/seller_data_pipeline/ingestion/
  字段映射、schema guard、dry-run preview、入库编排。

src/seller_data_pipeline/db/
  Azure SQL 连接、SQL 执行、repository、upsert。

tests/
  单元测试和集成测试。单元测试不依赖真实 Amazon / Azure。
```

## 7. 当前真实状态

截至 2026-05-17：

| 模块 | 状态 | 说明 |
|---|---|---|
| SP-API 连接测试 | 已实现 | 可验证 `marketplaceParticipations`。 |
| SP-API Reports sampling | 已实现一批 | 已下载和分析多类 report，样例文档在 `requirements/data_samples/`。 |
| Amazon Ads sampling | 已实现 | 已获取 profile，并下载 Sponsored Products 多类报表。 |
| Azure SQL 初始建表 | 已完成 | `001` 和 `002` 已执行成功，当前 28 张表；连接层已支持 retry + `SELECT 1` warm-up。 |
| Ads normalized ingestion | 已完成第一条真实闭环 | 4 张 Ads SP 日表首次 inserted=200，重复执行 updated=200。 |
| 数据库状态检查脚本 | 已实现 | `scripts/check_database_status.py`。 |
| SP-API Listing normalized ingestion | 已完成 | Listing dry-run、execute、重复 execute 幂等性已通过：首次 inserted=6，第二次 updated=6。 |
| SP-API Inventory normalized ingestion | 已完成 | Inventory dry-run、execute、重复 execute 幂等性已通过：首次 inserted=5，第二次 updated=5。 |
| SP-API Sales & Traffic normalized ingestion | Implemented | `feature_sales_traffic_ingestion.md` 已建立；005 migration、专用 CLI/repository、dry-run、execute 和幂等性验证已完成。 |
| SP-API Settlement normalized ingestion | Implemented | Settlement dry-run、execute、重复 execute 幂等性已通过：首次 inserted=4911，第二次 updated=4911。 |
| SP-API Orders normalized ingestion | Implemented | Orders dry-run、execute、重复 execute 幂等性已通过：首次 inserted=112，第二次 updated=112。 |
| SP-API FBA Reimbursements normalized ingestion | Implemented | FBA Reimbursements dry-run、execute、重复 execute 幂等性已通过：首次 inserted=19，第二次 updated=19。 |
| 周报/月报/清仓分析 | 待设计/待开发 | 依赖 normalized 数据沉淀后再做。 |
| Azure Container Apps Jobs | 待开发 | 本地闭环稳定后再上云。 |

## 8. 下一阶段主线

下一阶段不应先做自动任务或报表，而应继续扩展 SP-API normalized 入库闭环。Listing、Inventory、Sales & Traffic、Settlement、Orders、FBA Reimbursements 已完成，下一条主线是 FBA Fee Preview：

```text
GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA
  -> feature_fba_fee_preview_ingestion.md 已建立
  -> amazon_fba_fee_preview 已建表
  -> 009_add_fba_fee_preview_business_key.sql 已执行，live schema 已导出
  -> 专用 dry-run/schema guard/repository/CLI 已开发并通过 dry-run
  -> dry-run / repository / execute 待开发
```

建议顺序：

1. 完成 FBA Fee Preview execute 与幂等验证
2. 通过后将 FBA Fee Preview 标记为 Implemented
3. 开始利润核算功能设计
4. 做财务利润计算、周报/月报、清仓决策支持。

## 9. 文档体系关系

本项目正式文档从现在开始维护在 `docs/`：

- 项目说明和开发规则：`docs/project/`
- 数据接入目录：`docs/data_access/`
- 单功能设计：`docs/features/`
- 当前数据库事实和 migration 规则：`docs/database/`
- 长期架构决策：`docs/adr/`

`requirements/` 下旧文档在迁移完成前仍可作为参考，但新开发不应继续把它作为唯一事实来源。


## Promotion/Coupon 与 Inventory Ledger 补充数据

2026-05-17 已新增两份功能设计并准备对应 migration：

```text
docs/features/feature_promotion_coupon_ingestion.md
sql/migrations/010_add_promotion_coupon_business_keys.sql

docs/features/feature_inventory_ledger_ingestion.md
sql/migrations/011_add_inventory_ledger_business_keys.sql
```

Promotion/Coupon 用于优惠券、折扣、会员日/Prime Day 等活动效果分析；Inventory Ledger 用于库存 movement 与库存审计。周报中的当前库存余额仍优先来自 `amazon_inventory_daily`，Ledger 用于解释库存变化。
