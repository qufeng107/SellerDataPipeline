# ADR-011: Use Azure Container Apps Jobs for First Automation Layer

> 状态：Accepted  
> 日期：2026-05-24  
> 相关文档：`docs/features/feature_automation_jobs_workflow.md`, `docs/operations/azure_container_apps_jobs_workflow.md`, `docs/adr/ADR-012-zero-paid-automation-storage-profile.md`

## Context

SellerDataPipeline 当前已经形成 CLI-first 的手动/半自动流程：

```text
run_manual_refresh_plan.py
-> ingestion scripts
-> report generation scripts
-> report delivery pack
-> send_report_email.py
```

这些流程依赖：

```text
Python CLI
Azure SQL / ODBC
Amazon SP-API / Ads async reports
runtime/ sampling manifests
reports/raw files
XLSX generation
SMTP attachment sending
```

项目现在需要迁移到云端自动运行，但公司体量小，第一版不能引入过重 orchestration 平台。

## Decision

第一版自动化采用 Azure Container Apps Jobs。

不采用：

```text
Azure Functions / Durable Functions
Airflow
Logic Apps
自建 Celery beat worker
Kubernetes CronJob
```

## Rationale

1. Container Apps Jobs 可以直接运行现有 Docker image 和 CLI 命令。
2. Jobs 是短生命周期任务模型，适合 submit / collect / ingest / report / send 这种 run-to-completion 脚本。
3. Amazon report 本身是异步生成，拆 job 比一个长时间常驻 worker 更容易排错。
4. 当前项目需要共享 runtime 和 reports 文件，Container Jobs + Azure Files 与本地运行模型最接近。
5. Azure Functions Timer 虽可做 schedule，但需要更早改造函数入口、依赖和文件模型；当前收益不如 Container Apps Jobs。

## Consequences

需要额外处理：

```text
1. Azure Files 挂载，保证不同 job execution 共享 runtime/reports。
2. Azure SQL 出站 IP allowlist。
3. Azure Container Apps secrets / Key Vault 管理敏感配置。
4. Job schedule 的先后顺序和 retry 间隔。
```

不会改变：

```text
1. Settlement-led 财务口径。
2. Normalized upsert 覆盖当前版本。
3. 三类管理报表 JSON + XLSX 输出。
4. SMTP send guard 和 DB recipient routing。
5. 先 dry-run 再 execute 的开发原则。
```


## 2026-05-24 Revision

ADR-011 仍然确认第一版自动化使用 Azure Container Apps Jobs。

成本与持久化策略由 ADR-012 修订：

```text
Image registry: GHCR instead of ACR v1
Persistent files: Azure SQL artifact store instead of Azure Files v1
Firewall: Azure SQL Allow Azure services rule for v1
```

因此，本文中原先提到的 Azure Files / fixed outbound IP 是未来增强方向，不是 v1 free-first profile 的实现要求。
