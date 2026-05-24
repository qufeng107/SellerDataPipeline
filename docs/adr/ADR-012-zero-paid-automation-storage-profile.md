# ADR-012: Use Zero-Paid Automation Profile for First Cloud Jobs

> 状态：Accepted  
> 日期：2026-05-24  
> 相关文档：`docs/features/feature_automation_jobs_workflow.md`, `docs/operations/azure_container_apps_jobs_workflow.md`, `docs/adr/ADR-011-azure-container-apps-jobs-automation.md`

## Context

SellerDataPipeline 已完成三类管理报表、Report Delivery、SMTP 发送和数据库收件人路由。下一步需要把手动/半自动流程迁移到云端自动运行。

公司处于早期阶段，当前明确约束是：

```text
优先使用免费额度；
不希望引入任何确定性的新增月费；
不要上来使用 Azure Files / ACR / NAT Gateway / Private Endpoint 等可能带来固定或额外费用的组件。
```

同时，当前脚本依赖本地文件系统：

```text
runtime/sampling manifests
reports/raw files
analysis_reports JSON/XLSX
report_delivery packs
send_result.json
```

Container Apps Job execution 是短生命周期运行，job 退出后本地文件不可作为下一 job 的持久状态。

## Decision

第一版自动化采用 free-first / zero-paid-preferred profile：

```text
Runtime: Azure Container Apps Jobs consumption plan
Image registry: GitHub Container Registry (GHCR), not Azure Container Registry v1
Artifact persistence: Azure SQL artifact store, not Azure Files / Blob v1
Database: current Azure SQL free database
Firewall: Allow Azure services rule, start/end IP 0.0.0.0
Deployment: GitHub Actions CI/CD updates Container Apps Jobs
```

新增 planned table：

```text
dbo.pipeline_artifact_store
```

用途：保存跨 job 需要共享的文件产物，内容 gzip 压缩后存 `VARBINARY(MAX)`，并配合 `expires_at` 做保留期控制。

## Rationale

1. Azure Container Apps Jobs 的 consumption plan 有月度免费额度，适合低频短任务。
2. Azure SQL free database 已存在，短期 raw reports / XLSX / JSON 文件量很小，可用作低成本 artifact store。
3. Azure Files 更适合共享文件系统，但会引入额外 storage 资源，不符合当前“零新增费用优先”。
4. ACR 更适合 Azure 原生镜像管理，但 v1 可用 GHCR 避免新增 ACR 资源。
5. 0.0.0.0/0.0.0.0 Azure SQL firewall rule 简化 Azure Jobs 访问数据库，不需要 NAT Gateway / fixed outbound IP。
6. 该方案保留将来迁移空间：artifact store 可从 `content_bytes` 演进为 `blob_uri + metadata`。

## Consequences

优点：

```text
1. 不引入 Azure Files / Blob / ACR 基础资源。
2. 继续复用现有 Python CLI 和相对路径。
3. job 之间有可审计的 artifact 交接记录。
4. 可先在本地模拟 save/restore，再迁移到 Azure Jobs。
```

缺点：

```text
1. Azure SQL 会承载文件内容，必须控制大小和 retention。
2. artifact store 不适合长期保存大量 raw reports。
3. SQL backup/storage free quota 会被 artifact 占用。
4. 0.0.0.0 Allow Azure services 不是严格最小网络暴露。
5. GHCR private package 可能受 GitHub account quota 影响；需监控镜像大小。
```

## Migration triggers

当出现以下任一情况时，必须重新评估架构：

```text
Azure SQL database storage approaching 20GB
pipeline_artifact_store monthly growth > 1GB
需要保存 raw reports 超过 12 个月
需要多人直接下载历史附件
邮件附件或 raw reports 体积明显变大
需要通过安全审计或客户/会计长期留档
需要更严格网络边界
```

未来迁移方向：

```text
Artifact content -> Azure Blob / Azure Files
pipeline_artifact_store -> metadata/hash/URI index
Networking -> NAT Gateway fixed outbound IP or Private Endpoint
Image registry -> ACR if GHCR quota/availability becomes issue
```


## 2026-05-24 cadence addendum

自动化周期改为 report-driven：

```text
Weekly stats window: Saturday-Friday, 上上周六到上周五。
Weekly request window: stats_start - 3 days to stats_end, 上上周三到上周五。
Monthly window: previous calendar month, scheduled on day 3.
```

第一版代码新增 `run_automation_stage.py` 和 `pipeline_artifact_store`，但 Azure resources/schedules 仍需后续创建。
