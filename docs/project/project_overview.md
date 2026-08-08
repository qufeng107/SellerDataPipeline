# SellerDataPipeline 项目总览

> 更新时间：2026-08-08  
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
- 使用 schema guard 检查字段漂移：additive new fields 保持可观测但不中断生产，required contract 缺失或关键语义/解析变化才阻断，避免静默写错库。
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

截至 2026-06-01，核心数据底座已经完成，报表层和第一层 Azure Jobs dev rollout 也已进入可验证阶段。已通过真实 Azure SQL execute 和第二次 execute 幂等性验证的模块包括：

| 模块 | 状态 | 说明 |
|---|---|---|
| SP-API 连接测试 | 已实现 | 可验证 `marketplaceParticipations`。 |
| SP-API Reports sampling | 已实现一批 | 已下载和分析多类 report，历史样例在 `requirements_to_be_deprecated/data_samples/`。 |
| Amazon Ads sampling | 已实现 | 已获取 profile，并下载 Sponsored Products 多类报表。 |
| Azure SQL 基础设施 | 已完成 | `001`-`012` 已执行成功，当前 29 张用户表；连接层支持 retry + warm-up。 |
| Ads normalized ingestion | Implemented | 4 张 Ads SP 日表首次 inserted=200，重复执行 updated=200。 |
| Listing normalized ingestion | Implemented | 首次 inserted=6，重复执行 updated=6。 |
| Inventory snapshot ingestion | Implemented | 首次 inserted=5，重复执行 updated=5。 |
| Sales & Traffic ingestion | Implemented | 首次 inserted=7，重复执行 updated=7。 |
| Settlement ingestion | Implemented | 首次 inserted=4911，重复执行 updated=4911。 |
| Orders ingestion | Implemented | 首次 inserted=112，重复执行 updated=112。 |
| FBA Reimbursements ingestion | Implemented | 首次 inserted=19，重复执行 updated=19。 |
| FBA Fee Preview ingestion | Implemented | 首次 inserted=8，重复执行 updated=8。 |
| Promotion/Coupon ingestion | Implemented | 首次 inserted=10，重复执行 updated=10。 |
| Inventory Ledger ingestion | Implemented | Summary + Detail 首次 inserted=357，重复执行 updated=357。 |
| Manual operations workflow | Planned / documented | 已建立手动执行流程和数据更新周期目录。 |
| Job cadence config table | Implemented | `012_create_ingestion_job_config.sql` 和 seed 001 已执行；seed 002 用于同步重叠窗口刷新策略。 |
| 利润核算 | Preview implemented | 已冻结 Settlement-led Financial Profit v1.0；第一版手动利润 preview 已实现。 |
| 周报/月报/广告优化报表 | Implemented / pending live verification | Monthly Financial Close v1.2、WBR v1.1、WAOR v1.1 已实现；下一步用真实周期重新生成并复核。 |
| Azure Container Apps Jobs | Manual dev rollout in progress | GHCR dev image、sdp-smoke-dev、sdp-weekly-submit-dev 已验证；下一步 collect/ingest 与 report delivery dev jobs。 |

## 8. 下一阶段主线

核心 normalized ingestion 已收尾。下一阶段采用 manual-first 策略：

```text
手动下载 raw data
-> 手动入库 normalized tables
-> 每 2 天核心源重叠刷新
-> 每周手动加工利润 preview 和周报
-> 手动复核并发送邮件
-> 再迁移到 Azure Container Apps Jobs
```

建议顺序：

1. 执行 seed 002 更新 `pipeline_job_config` 刷新窗口，再运行 stable coverage audit 确认 2026 YTD 覆盖。
2. 录入/导入 SKU 成本与头程/海运成本，并验证缺成本阻塞规则。
3. 用真实周期数据人工复核利润 preview，分析产物最短按周。
4. 开发手动周报/月报输出。
5. 先人工复核和邮件发送，再自动化 Jobs。

## 9. 文档体系关系

本项目正式文档从现在开始维护在 `docs/`：

- 项目说明和开发规则：`docs/project/`
- 数据接入目录：`docs/data_access/`
- 单功能设计：`docs/features/`
- 当前数据库事实和 migration 规则：`docs/database/`
- 长期架构决策：`docs/adr/`

`requirements_to_be_deprecated/` 下旧文档暂时作为历史取样和旧设计参考；新开发不应继续把它作为唯一事实来源，删除计划见 `docs/project/requirements_deprecation_plan.md`。


## 2026-08-08 Reliability update

- v1.79 Schema Guard compatibility policy has passed Azure weekly production verification.
- v1.81 monthly recovery hardens Settlement idempotency/rollback semantics and adds an explicit exact-duplicate repair command before backfilling June/July monthly reports.
