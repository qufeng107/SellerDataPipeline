# 功能设计文档索引

> 更新时间：2026-05-25  
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
| [`feature_ingestion_job_config.md`](feature_ingestion_job_config.md) | Implemented | 数据下载/入库/加工/报表任务周期配置表；012 migration 和 seed 001 已执行，seed 002 用于同步重叠窗口刷新策略。 |
| [`feature_profit_calculation.md`](feature_profit_calculation.md) | Preview implemented | 利润核算口径已冻结为 Settlement-led Financial Profit v1.0；第一版 `calculate_profit_report.py` 已实现文件型 preview，不落利润结果表。 |
| [`feature_sku_cost_management.md`](feature_sku_cost_management.md) | Implemented | SKU 成本 xlsx 模板导出与导入；默认 dry-run、按 marketplace + SKU + effective_from 幂等写入 `amazon_sku_cost`。 |
| [`feature_monthly_financial_close_report.md`](feature_monthly_financial_close_report.md) | Implemented / pending live verification | 月度财务结算报表设计；基于 Settlement-led Financial Profit，按月输出 CEO/CFO 管理口径 P&L、费用结构、SKU 利润和对账检查；v1 默认输出 JSON + 单个 XLSX 多 sheet。 |
| [`feature_weekly_business_review.md`](feature_weekly_business_review.md) | Implemented / pending live verification | 每周经营周报 v1；自然周销售、流量、订单、广告、SKU、库存和风险行动建议，定位为 CEO/运营负责人每周复盘；默认输出 JSON + 单个 XLSX 多 sheet。 |
| [`feature_weekly_ads_optimization_report.md`](feature_weekly_ads_optimization_report.md) | Implemented / pending live verification | 每周广告优化报表 v1；Sponsored Products campaign、targeting、search term、advertised product 维度分析，输出否词/加词/调价/观察动作清单；默认输出 JSON + 单个 XLSX 多 sheet，不调用 Ads 写接口。 |
| [`feature_report_delivery_email.md`](feature_report_delivery_email.md) | Implemented v1.3 | 统一报表交付/邮件草稿包；已支持从三类报表 JSON 生成不同模板邮件正文、manifest 和 XLSX 附件包。SMTP 发送已实现，收件人从 `report_email_recipient_config` 读取；v1.3 增加中英文双语邮件正文和 XLSX 固定标签/说明。 |
| [`feature_pipeline_artifact_store.md`](feature_pipeline_artifact_store.md) | Implemented | free-first 自动化 artifact store；migration 014 已执行，使用 Azure SQL 压缩保存 manifests/raw reports/report packs，替代 Azure Files v1。 |
| [`feature_automation_jobs_workflow.md`](feature_automation_jobs_workflow.md) | Manual dev rollout in progress | Azure Container Apps Jobs 自动化工作流设计；GHCR dev image、sdp-smoke-dev、sdp-weekly-submit-dev 已验证，下一步创建 collect_ingest/report_delivery dev jobs。 |
| Historical backfill CLI | Implemented | `scripts/backfill_report_requests.py` / `scripts/backfill_ads_reports.py`；按明确日期范围分段提交历史补数请求，详见 `docs/operations/historical_backfill_workflow.md`。 |

## 3. 下一批建议

当前核心 ingestion 功能已全部完成。后续优先级应切换为：

1. 执行 `sql/seeds/002_update_ingestion_job_config_refresh_policy.sql`，使 `pipeline_job_config` 与重叠窗口刷新策略一致。
2. 运行 `scripts/audit_data_coverage.py --target-start-date 2026-01-01`，按 stable cutoff 判断 2026 YTD 数据覆盖。
3. 使用 historical backfill CLI 按明确日期范围补 Orders / Ads 等历史缺口，并对最近 10/14/30/60 天做 rolling refresh。
4. 使用 `feature_sku_cost_management.md` 维护 SKU 成本，并验证缺成本阻塞规则。
5. 用真实 3月/4月或 5月上旬数据人工复核利润 preview。
6. 当前已冻结并优化三份管理报表设计。Monthly Financial Close Report v1 已完成代码实现，并根据 2026-03 / 2026-04 真实输出复核补充 Ads API context 缺失 warning、console reconciliation 计数和 SKU Profit scope note；Weekly Business Review v1 已实现 JSON + 单个 XLSX 多 sheet 输出，并用 2026-05-11..2026-05-17 真实数据生成 status=ok；Weekly Ads Optimization Report v1 已实现 JSON + 单个 XLSX 多 sheet 输出，并已使用 2026-05-11..2026-05-17 真实 Ads 数据生成 status=ok；统一 Report Delivery / Email Pack v1 草稿包已实现；SMTP 真实发送已实现，新增 `send_report_email.py`，使用 Python 标准库 SMTP，并通过数据库表 `report_email_recipient_config` 按 `report_type + audience` 配置收件人；v1.3 增加中英文双语邮件和 XLSX 固定标签/说明。
7. 三类管理报表与 Report Delivery 已完成第一轮真实验证：WAOR 双语邮件和 XLSX 附件已通过 SMTP 成功发送。Azure Container Apps Jobs 已进入 manual dev rollout：GHCR dev image、`sdp-smoke-dev`、`sdp-weekly-submit-dev` 均已成功。下一步创建 `sdp-weekly-collect-ingest-dev` 与 `sdp-weekly-report-delivery-dev`，详见 `feature_automation_jobs_workflow.md` 和 `docs/operations/azure_container_apps_jobs_workflow.md`。后续报表默认遵循 JSON + 单个 XLSX 多 sheet，避免 Markdown 和多个 CSV 文件碎片化。

注意：数据刷新可以每 1-2 天执行一次；销售、广告、利润等正式分析产物最短周期为一周。


### Automation note

`feature_automation_jobs_workflow.md` 已在 2026-05-25 更新为 manual dev rollout 状态：v1 使用 GHCR + Azure SQL artifact store，不使用 Azure Files / ACR；`sdp-smoke-dev` 与 `sdp-weekly-submit-dev` 已成功。复制后续 jobs 时优先使用 Azure CLI 模板，不建议继续在 Portal 手动重复填写。
