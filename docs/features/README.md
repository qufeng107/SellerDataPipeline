# 功能设计文档索引

> 更新时间：2026-08-09  
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
| [`feature_schema_guard_resilience.md`](feature_schema_guard_resilience.md) | Implemented / Azure verified | additive new fields non-blocking，required contract 缺失/关键解析或语义变化才阻断；已通过 main 镜像 weekly Azure 验收。 |
| [`feature_listing_snapshot_ingestion.md`](feature_listing_snapshot_ingestion.md) | Implemented | SP-API `GET_MERCHANT_LISTINGS_ALL_DATA` -> `amazon_listing_snapshot`；dry-run、schema guard、repository、CLI、真实 Azure SQL execute 和幂等性验证已完成。 |
| [`feature_inventory_ingestion.md`](feature_inventory_ingestion.md) | Implemented v1.1 / Azure verification pending | Inventory snapshot v1.1 已采用 minimal required contract；Amazon additive fields 仅 warning，不再阻断。 |
| [`feature_sales_traffic_ingestion.md`](feature_sales_traffic_ingestion.md) | Implemented v1.1 / Azure verification pending | Sales & Traffic v1.1 已采用 minimal required contract；2026-08-03 的 24 个 additive path 回归不再阻断。 |
| [`feature_settlement_ingestion.md`](feature_settlement_ingestion.md) | Implemented / v1.88 correctness hardening pending Azure verification | SP-API `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` -> `amazon_settlement_transaction`；v1.88 增加显式日期解析、US/USD 内容 guard、同 report raw copy 去重与 late discovery recovery。 |
| [`feature_settlement_correctness_late_discovery.md`](feature_settlement_correctness_late_discovery.md) | Implemented locally / Azure verification pending | v1.88：修复 Settlement 跨月日期误解析、foreign-currency attribution、同 report 多 raw path 重复与月末 late-generated Settlement 漏发现。 |
| [`feature_finances_api_natural_month_sampling.md`](feature_finances_api_natural_month_sampling.md) | Completed / superseded by v1.90 ledger | v1.89：Finances API live sampling 已完成 May/Jun/Jul Seller Central reconciliation。 |
| [`feature_finances_api_natural_month_ledger.md`](feature_finances_api_natural_month_ledger.md) | v1.90.2 local fix / Azure Gate 4 revalidation pending | Natural-month Finances ledger + Management P&L；Gate 2/3 已通过，v1.90.2 增加 FNSKU -> canonical Seller SKU 成本身份解析。 |
| [`feature_orders_ingestion.md`](feature_orders_ingestion.md) | Implemented | SP-API `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` -> `amazon_order_item`；007、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_fba_reimbursements_ingestion.md`](feature_fba_reimbursements_ingestion.md) | Implemented | SP-API `GET_FBA_REIMBURSEMENTS_DATA` -> `amazon_fba_reimbursement`；008、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_fba_fee_preview_ingestion.md`](feature_fba_fee_preview_ingestion.md) | Implemented | SP-API `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` -> `amazon_fba_fee_preview`；009、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_promotion_coupon_ingestion.md`](feature_promotion_coupon_ingestion.md) | Implemented | SP-API Promotion/Coupon reports -> 4 张促销/优惠券表；010、dry-run、execute 和第二次 execute 幂等性验证已完成。 |
| [`feature_inventory_ledger_ingestion.md`](feature_inventory_ledger_ingestion.md) | Implemented | SP-API Inventory Ledger summary/detail -> 2 张库存流水表；011 已执行，专用 ingestion 已完成 execute/幂等验证。 |
| [`feature_ingestion_job_config.md`](feature_ingestion_job_config.md) | Implemented | 数据下载/入库/加工/报表任务周期配置表；012 migration 和 seed 001 已执行，seed 002 用于同步重叠窗口刷新策略。 |
| [`feature_profit_calculation.md`](feature_profit_calculation.md) | Preview implemented | 利润核算口径已冻结为 Settlement-led Financial Profit v1.0；第一版 `calculate_profit_report.py` 已实现文件型 preview，不落利润结果表。 |
| [`feature_sku_cost_management.md`](feature_sku_cost_management.md) | Implemented | SKU 成本 xlsx 模板导出与导入；默认 dry-run、按 marketplace + SKU + effective_from 幂等写入 `amazon_sku_cost`。 |
| [`feature_monthly_financial_close_report.md`](feature_monthly_financial_close_report.md) | Implemented v1.4 locally / Azure correctness recovery pending | 月度财务结算报表；v1.4 在 v1.3 Executive P&L / landed COGS 上增加 Settlement explicit-date + expected-currency query guard，等待 v1.88 历史修复后重新关闭 2026-05/06/07。 |
| [`feature_monthly_executive_pnl_landed_cogs.md`](feature_monthly_executive_pnl_landed_cogs.md) | Implemented locally / Azure verification pending | v1.87：月报经营口径升级；Management Operating Profit 作为首页主指标，拆分商品/头程/包装/其他到岸COGS，并更新邮件利润口径。 |
| [`feature_monthly_ingestion_recovery.md`](feature_monthly_ingestion_recovery.md) | Implemented locally / Azure recovery pending | v1.81：Settlement canonical-key MERGE、rollback 语义、exact duplicate repair；Promotion/Coupon additive drift 回归；用于恢复 2026-06 / 2026-07 月报。 |
| [`feature_monthly_chunk_completeness_recovery.md`](feature_monthly_chunk_completeness_recovery.md) | Implemented locally / Azure verification pending | v1.83：修复 Monthly Sales/Orders/Ads 多分片只入最新文件、历史月份 coverage window 过宽、Ads timing 误阻断邮件。 |
| [`feature_settlement_repair_scalability.md`](feature_settlement_repair_scalability.md) | Implemented locally / Azure verification pending | v1.82：针对 3,878 个历史 Settlement duplicate groups，将 repair 从 N+1 SQL 改为 single-scan + bounded batch DML，并限制默认日志输出。 |
| [`feature_settlement_ingestion_batch_upsert.md`](feature_settlement_ingestion_batch_upsert.md) | Superseded | v1.84：Azure 验证发现 1950-parameter staging INSERT 和 duplicate fallback 仍过慢，已由 v1.85 替代。 |
| [`feature_settlement_ingestion_json_upsert.md`](feature_settlement_ingestion_json_upsert.md) | Implemented / Azure verified | v1.85：exact duplicate collapse + typed OPENJSON bounded batches + set-based MERGE；2026-06/07 recovery 已通过 Azure 生产验收。 |
| [`feature_settlement_fba_fee_classification.md`](feature_settlement_fba_fee_classification.md) | Implemented locally / Azure verification pending | v1.86：补齐 `FBA Inventory Storage Fee` 与 `FBA Customer Returns Fee (...)` 的保守分类，消除已确认的 2026-07 `-35.45` unknown/unclassified。 |
| [`feature_weekly_business_review.md`](feature_weekly_business_review.md) | Implemented v1.1 / pending live verification | 每周经营周报；默认 Saturday-Friday，贡献指标明确为“广告和货本后贡献，未扣完整 Amazon 平台费”，默认输出 JSON + 单个 XLSX 多 sheet。 |
| [`feature_weekly_ads_optimization_report.md`](feature_weekly_ads_optimization_report.md) | Implemented v1.1 / pending live verification | 每周广告优化报表；已支持 active action / historical paused lessons 拆分、negative keyword snapshot 去重和 `--negative-keyword-csv`，默认输出 JSON + 单个 XLSX 多 sheet，不调用 Ads 写接口。 |
| [`feature_report_delivery_email.md`](feature_report_delivery_email.md) | Implemented v1.3 | 统一报表交付/邮件草稿包；已支持从三类报表 JSON 生成不同模板邮件正文、manifest 和 XLSX 附件包。SMTP 发送已实现，收件人从 `report_email_recipient_config` 读取；v1.3 增加中英文双语邮件正文和 XLSX 固定标签/说明。 |
| [`feature_pipeline_artifact_store.md`](feature_pipeline_artifact_store.md) | Implemented | free-first 自动化 artifact store；migration 014 已执行，使用 Azure SQL 压缩保存 manifests/raw reports/report packs，替代 Azure Files v1。 |
| [`feature_automation_jobs_workflow.md`](feature_automation_jobs_workflow.md) | Manual dev rollout in progress | Azure Container Apps Jobs 自动化工作流设计；GHCR dev image、sdp-smoke-dev、sdp-weekly-submit-dev 已验证，下一步创建 collect_ingest/report_delivery dev jobs。 |
| [`feature_pipeline_job_run_audit_log.md`](feature_pipeline_job_run_audit_log.md) | Implemented / first cloud rows pending | 自动化 Job Run 结构化审计账本；migration 015 已执行并导出 live schema，repository/service/wrapper audit hooks 已接入，等待新镜像 dev job 写入首批审计记录。 |
| Historical backfill CLI | Implemented | `scripts/backfill_report_requests.py` / `scripts/backfill_ads_reports.py`；按明确日期范围分段提交历史补数请求，详见 `docs/operations/historical_backfill_workflow.md`。 |

## 3. 下一批建议

当前优先级为 v1.90.2 Finances cost identity Gate 4 revalidation：

1. CI 通过后构建 v1.90.2 image；永久 monthly jobs 暂保持当前稳定镜像。
2. 已完成 Gate 2 / Gate 3A / Gate 3B；现有 652 行 Finances ledger 不需要重写。
3. 仅重跑 2026-05 / 06 / 07 Monthly Financial Close preview。
4. 必须确认三个月 `missing_cost_skus=[]`、costed units 为 99 / 122 / 62，并审计 `cost_identity_resolutions`。
5. 三个月 `status=ok` 后再更新正式 monthly jobs；历史月报不 `force-resend`。


不补发历史 weekly；weekly 从当前周期继续。


注意：数据刷新可以每 1-2 天执行一次；销售、广告、利润等正式分析产物最短周期为一周。


### Automation note

`feature_automation_jobs_workflow.md` 已在 2026-05-25 更新为 manual dev rollout 状态：v1 使用 GHCR + Azure SQL artifact store，不使用 Azure Files / ACR；`sdp-smoke-dev` 与 `sdp-weekly-submit-dev` 已成功。复制后续 jobs 时优先使用 Azure CLI 模板，不建议继续在 Portal 手动重复填写。
