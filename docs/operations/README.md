# Operations Runbooks

> 文档定位：记录人工执行、半自动执行和未来自动化 Jobs 的运行流程。这里不定义业务口径；业务口径见 `docs/features/`。这里不记录真实数据库字段；真实 schema 见 `docs/database/database_current_schema_spec.md`。

## 当前文档

| 文档 | 用途 |
|---|---|
| `manual_execution_workflow.md` | 本地/人工执行数据下载、入库、加工报表和邮件发送的标准流程。 |
| `data_refresh_policy.md` | 数据源滚动刷新、upsert 覆盖、stable cutoff 与周报/月报加工节奏。 |
| `ingestion_job_cadence_catalog.md` | 每类数据项的建议下载/入库周期、数据窗口和未来自动化频率。 |
| `data_coverage_audit_workflow.md` | 利润/周报前如何审计 normalized 数据覆盖范围和 stable cutoff。 |
| `historical_backfill_workflow.md` | 按明确日期范围分段提交 SP-API / Ads 历史补数请求，替代人工倒推 `--days`。 |
| `manual_refresh_plan_workflow.md` | 标准“简单几个指令定期下载所有数据入库”流程，定义 `core_rolling` / `weekly_full` plan 和 submit/collect/ingest/audit phase。 |
| `azure_container_apps_jobs_workflow.md` | Azure Container Apps Jobs 自动化 runbook；按数据下载、数据入库、报表与发送三阶段迁移手动流程。 |
| `azure_container_apps_jobs_setup_checklist.md` | Azure Container Apps Jobs 开通、GHCR 镜像、环境变量/secrets、manual job 命令和 schedule 的落地清单。 |

## 当前原则

当前项目进入“手动可重复执行”阶段，自动化 Jobs 之前必须先满足：

```text
手动下载 raw data
-> 手动入库 normalized tables
-> 手动刷新/复核覆盖范围
-> 手动加工利润 preview 和周报/月报
-> 手动复核并发送邮件
-> 再迁移到 Azure Container Apps Jobs
```

数据刷新和分析产物频率已明确分离：

```text
数据刷新：可以每 1-2 天执行一次，使用重叠窗口 + upsert 覆盖。
分析产物：销售周报、广告周报、利润周报/月报最短周期为一周。
```

自动化不应改变业务逻辑，只应复用已经通过手动验收的 CLI、配置和审计表。利润核算当前采用 Settlement-led Financial Profit v1.0，第一版必须先人工复核后再进入周报或邮件。


## 标准定期更新入口

定期刷新不再临时拼零散脚本，统一使用：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase collect --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase audit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --target-start-date 2026-03-01 --execute
```

每周完整刷新把 `--plan core_rolling` 替换为 `--plan weekly_full`。详见 `manual_refresh_plan_workflow.md`。


## 未来自动化入口

Azure Container Apps Jobs 自动化方案见：

```text
docs/features/feature_automation_jobs_workflow.md
docs/operations/azure_container_apps_jobs_workflow.md
docs/adr/ADR-011-azure-container-apps-jobs-automation.md
```

第一版自动化仍然遵循手动优先原则：先创建 manual-triggered jobs 并手动触发验证，再启用 schedule；先只发给 `feng@cuidena.cn` 测试，再恢复数据库收件人默认三人。


## Azure Jobs automation note

`azure_container_apps_jobs_workflow.md` 已在 2026-05-24 修订为 free-first profile：

```text
Azure Container Apps Jobs consumption plan
+ GHCR image
+ Azure SQL artifact store
+ SMTP delivery
```

v1 不使用 Azure Files / Blob / ACR / NAT Gateway / Private Endpoint。跨 job 的 runtime/reports 文件通过计划中的 `dbo.pipeline_artifact_store` 压缩持久化。
