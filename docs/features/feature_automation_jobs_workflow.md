# Feature: Automated Workflow Jobs

> 文档状态：Implemented / production running  
> 负责人：AI + Feng  
> 更新时间：2026-08-10  
> 功能状态：weekly/monthly Azure Container Apps Jobs running; monthly v1.90.3 final production smoke verified  
> 相关 operations：`docs/operations/manual_refresh_plan_workflow.md`, `docs/operations/azure_container_apps_jobs_workflow.md`, `docs/operations/data_refresh_policy.md`  
> 相关功能：`feature_pipeline_artifact_store.md`, `feature_report_delivery_email.md`, `feature_weekly_business_review.md`, `feature_weekly_ads_optimization_report.md`, `feature_monthly_financial_close_report.md`  
> 相关 ADR：`docs/adr/ADR-007-manual-first-before-automation.md`, `docs/adr/ADR-011-azure-container-apps-jobs-automation.md`, `docs/adr/ADR-012-zero-paid-automation-storage-profile.md`

---

## 0.1 2026-08-10 production note

Monthly official jobs now run the same v1.90.3 image SHA `2fa19ad316720742d1871765fa0c1149c6b9fb9a`. `sdp-monthly-collect-ingest` is fail-closed and no longer uses `--continue-on-error`. July final smoke execution `sdp-monthly-collect-ingest-cbacfwp` ended `Succeeded`, `commands=11 failed=0`, and artifact save completed 169/169. See `docs/operations/v190_natural_month_finances_rollout.md`.

## 1. 功能摘要

Automated Workflow Jobs 是 SellerDataPipeline 从“手动/半自动”进入“云端自动运行”的第一版自动化层。

它不重新定义任何数据口径，也不重写 ingestion、report 或 email 逻辑，而是把已经人工验证过的 CLI 固化到云端 job 中运行：

```text
Stage 1 数据下载 / Data download
  -> submit Amazon SP-API / Ads report requests
  -> collect ready raw reports
  -> persist request manifests and raw files into Azure SQL artifact store

Stage 2 数据入库 / Data ingestion
  -> restore raw files from Azure SQL artifact store into local job workspace
  -> ingest downloaded raw reports into Azure SQL normalized tables
  -> run coverage audit

Stage 3 数据报表与发送 / Reporting & delivery
  -> generate WBR / WAOR / Monthly Close JSON + XLSX in local job workspace
  -> persist report artifacts / delivery pack to Azure SQL artifact store
  -> send email through SMTP using DB recipient routing
```

第一版目标是：

```text
1. 保持手动流程仍可用。
2. Azure Jobs 只调度已验证脚本，不创建另一套业务逻辑。
3. 先支持 manual-triggered jobs，再启用 scheduled jobs。
4. 每个阶段都可单独运行、重跑、排错。
5. 数据下载、入库、报表发送三部分解耦。
6. 公司初期尽量使用免费额度，不引入 Azure Files / ACR 等可能产生基础费用的组件。
```

---

## 1.1 2026-05-25 implementation evidence

当前实现与云端验证状态：

```text
Code:
  scripts/run_automation_stage.py implemented
  scripts/manage_pipeline_artifacts.py implemented
  pipeline_artifact_store repository/service implemented
  --email-to override implemented for report_delivery smoke tests

Database:
  014_create_pipeline_artifact_store.sql executed
  database_current_schema_spec.md updated after live schema export
  pipeline_artifact_store used as Azure SQL artifact store

Report delivery:
  WBR / WAOR / Monthly Close output date-stamped JSON/XLSX
  Report Delivery bilingual email and XLSX labels verified
  SMTP sending verified with feng@cuidena.cn

GHCR:
  ghcr.io/qufeng107/seller-data-pipeline:dev built successfully from dev branch
  dev branch no longer pushes latest
  main branch will later publish latest/main

Azure manual dev jobs:
  sdp-smoke-dev succeeded
  sdp-weekly-submit-dev succeeded
  sdp-weekly-collect-ingest-dev pending
  sdp-weekly-report-delivery-dev pending
```

`sdp-weekly-submit-dev` 已验证：

```text
weekly_window=stats=2026-05-16..2026-05-22 request=2026-05-13..2026-05-22
SP-API Sales & Traffic submitted
SP-API Orders submitted
SP-API Inventory snapshot submitted
Ads reports submitted total=5
commands=4 failed=0
artifact_save scanned=8 saved=8 skipped=0
```

Portal command/args 经验已冻结：

```text
Command override = /bin/sh
Arguments override = -c, python scripts/run_automation_stage.py ...
```

下一步不是 schedule，而是 manual dev jobs 继续验证：

```text
1. SQL 查询 pipeline_artifact_store 是否包含 Azure submit artifacts。
2. 创建 sdp-weekly-collect-ingest-dev。
3. 创建 sdp-weekly-report-delivery-dev，先只发 feng@cuidena.cn。
4. weekly dev 三阶段稳定后再创建 monthly dev jobs。
5. 最后再新增 main-only deploy workflow。
```


## 2. v1 Free-first profile 冻结结论

2026-05-24 重新评估成本后，自动化第一版采用 **free-first / zero-paid-preferred profile**。

冻结选择：

```text
Runtime platform: Azure Container Apps Jobs consumption plan
Image registry: GitHub Container Registry (GHCR), not Azure Container Registry v1
Persistent artifacts: Azure SQL artifact store, not Azure Files v1
Database: existing Azure SQL free database
Firewall: Azure SQL Allow Azure services rule, start/end IP 0.0.0.0
Secrets: Azure Container Apps Job secrets + GitHub Actions secrets
Deployment: GitHub Actions builds image, pushes GHCR, updates Azure Jobs
```

暂不使用：

```text
Azure Files
Azure Blob Storage
Azure Container Registry
NAT Gateway / fixed outbound IP
Private Endpoint
Key Vault
Airflow / Durable Functions / Logic Apps
```

原因：

1. 当前公司初期预算优先级是“不新增确定性月费”。
2. Azure SQL free database 当前已有，且 raw reports / XLSX / JSON 文件量很小，短期可用数据库 artifact store 承载。
3. Azure Files 更贴近本地文件模型，但会引入额外 Storage account / file share 计费；v1 暂不使用。
4. ACR 更贴近 Azure 原生部署，但会引入 registry 资源；v1 使用 GHCR。
5. 防火墙 v1 先接受 `Allow Azure services` 的宽松边界，换取无需固定 IP / NAT Gateway 的低成本部署。

风险接受：

```text
此 profile 不是长期最优架构，而是低成本启动方案。
当文件量、任务频率、审计要求或安全要求上升时，应迁移到 Blob/Azure Files + fixed outbound IP/Private Endpoint。
```

---

## 2.1 Report-driven cadence 冻结

自动化周期跟着报表走，不再为了“尽可能刷新”而频繁下载所有源。

### Weekly reports

周报统计周期固定为 Saturday-Friday：

```text
stats window = 上上周六 .. 上周五（含首尾）
request window = stats_start - 3 days .. stats_end
即请求上上周三 .. 上周五，用三天 overlap 覆盖延迟和重算。
```

每周一调度：

```text
T+0h  weekly submit：提交 Sales & Traffic / Orders / Ads / Inventory 请求
T+2h  weekly collect_ingest #1：collect ready reports -> ingest -> audit
T+2.5h weekly collect_ingest #2：只重试一次 collect/ingest，仍失败则该源留 warning/partial
T+3h  weekly report_delivery：生成 WBR + WAOR -> delivery pack -> SMTP send
```

### Monthly reports

每月 3 日对上一个自然月执行完整数据获取：

```text
T+0h  monthly submit：提交/发现月度相关源，含 Settlement V2 discovery
T+2h  monthly collect_ingest #1
T+2.5h monthly collect_ingest #2
T+3h  monthly report_delivery：生成 Monthly Financial Close -> delivery pack -> SMTP send
```

月度源包括：

```text
Sales & Traffic
Orders
Ads
Settlement V2 discovery
FBA Reimbursements
Promotion/Coupon sampling
```

---


### 2.2 Email recipient override for cloud smoke tests

`run_automation_stage.py` supports a report-delivery-only recipient override:

```powershell
python scripts/run_automation_stage.py --workflow weekly --phase report_delivery --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute --send-email --email-to feng@cuidena.cn
```

Rules:

```text
1. `--email-to` is repeatable and also accepts comma-separated values.
2. It is passed through to `send_report_email.py --to ...`.
3. It is intended for Azure manual job smoke tests.
4. Once cloud jobs are stable, remove it so DB recipient routing controls recipients.
```

---

## 3. 为什么仍选择 Azure Container Apps Jobs

当前项目是 Python CLI + ODBC + Amazon asynchronous report + 本地 runtime/report files 的批处理管道。第一版自动化更适合使用 Azure Container Apps Jobs，而不是把所有逻辑改造成 GitHub Actions schedule 或 Azure Functions。

原因：

1. 当前代码已经是 CLI-first，Container Jobs 可以直接复用同一个 Docker image 和脚本命令。
2. Amazon SP-API / Ads report 是异步流程，submit、collect、ingest 天然适合拆成多个短生命周期 job execution。
3. Container Apps Jobs 可手动触发和 cron 定时，适合先手动 smoke test 再 schedule。
4. GitHub Actions 更适合 CI/CD，不适合作为长期业务调度器；GitHub runner 文件系统也不持久。
5. Azure Functions Timer 可以做定时任务，但会迫使项目更早改造成函数入口和 Functions runtime 依赖；当前阶段收益不高。

冻结结论：

```text
v1 automation platform = Azure Container Apps Jobs
v1 trigger = manual first, then schedule
v1 orchestration = simple job chain + Azure SQL artifact store
v1 CI/CD = GitHub Actions build/push/deploy
```

---

## 4. 总体架构

### 4.1 云端组件

```text
GitHub Actions
  -> run CI
  -> build Docker image
  -> push image to GitHub Container Registry (GHCR)
  -> update Azure Container Apps Jobs image/command/env

Azure Container Apps Environment
  -> Container Apps Jobs
  -> shared secrets / env vars
  -> ephemeral local workspace per execution

Azure SQL free database
  -> normalized business tables
  -> report_email_recipient_config
  -> pipeline_job_config
  -> planned pipeline_artifact_store

SMTP provider
  -> Tencent Exmail SMTP, smtp.exmail.qq.com:465 ssl
```

### 4.2 不再依赖共享文件盘

原设计使用 Azure Files 挂载：

```text
/app/runtime
/app/reports
```

free-first v1 改为：

```text
每个 job execution 使用临时本地 workspace。
跨 job 必须共享的文件写入 Azure SQL artifact store。
下一阶段 job 启动时从 artifact store restore 到本地 workspace。
```

这样可以保留现有 CLI 的本地文件读写模型，同时避免引入 Azure Files。

---

## 5. Azure SQL artifact store 设计

### 5.1 目标

`pipeline_artifact_store` 是自动化 v1 的轻量文件持久化层，用于替代 Azure Files。

它保存：

```text
runtime/sampling/report_requests/*.json
runtime/sampling/ads_report_requests/*.json
reports/raw/amazon/...
reports/raw/amazon_ads/...
runtime/analysis_reports/.../*.json
runtime/analysis_reports/.../*.xlsx
runtime/report_delivery/.../delivery_manifest.json
runtime/report_delivery/.../email_subject.txt
runtime/report_delivery/.../email_body.html
runtime/report_delivery/.../email_body.txt
runtime/report_delivery/.../attachments/*.xlsx
runtime/report_delivery/.../send_result.json
```

它不保存：

```text
secrets / .env
Python cache
large debug temp files
full historical logs without retention
```

### 5.2 Planned table

> 注意：本节是未来 migration 设计，不代表当前数据库已存在。执行 migration 后才能更新 `database_current_schema_spec.md`。

建议新增：

```text
dbo.pipeline_artifact_store
```

最小字段：

```sql
id BIGINT IDENTITY(1,1) PRIMARY KEY,
artifact_type NVARCHAR(80) NOT NULL,
artifact_scope NVARCHAR(200) NOT NULL,
relative_path NVARCHAR(600) NOT NULL,
content_type NVARCHAR(120) NULL,
content_encoding NVARCHAR(40) NOT NULL DEFAULT 'gzip',
content_sha256 CHAR(64) NOT NULL,
content_size_bytes BIGINT NOT NULL,
compressed_size_bytes BIGINT NOT NULL,
content_bytes VARBINARY(MAX) NOT NULL,
metadata_json NVARCHAR(MAX) NULL,
created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
expires_at DATETIME2 NULL,
archived_at DATETIME2 NULL,
is_deleted BIT NOT NULL DEFAULT 0
```

唯一键建议：

```sql
UNIQUE (artifact_scope, relative_path, content_sha256)
```

常用索引：

```sql
(artifact_type, artifact_scope, created_at DESC)
(relative_path, created_at DESC)
(expires_at) WHERE is_deleted = 0
```

### 5.3 Artifact type

建议枚举值：

```text
sp_report_request_manifest
ads_report_request_manifest
sp_raw_report
ads_raw_report
ingestion_preview
coverage_audit
analysis_report_json
analysis_report_xlsx
delivery_pack_file
email_send_result
```

### 5.4 Artifact scope

用于分组恢复文件，例如：

```text
marketplace=ATVPDKIKX0DER/report_type=GET_SALES_AND_TRAFFIC_REPORT/period=2026-05-11_2026-05-17
profile=3917953989967300/ads_report_type=spCampaigns/period=2026-05-11_2026-05-17
report=weekly_ads_optimization/marketplace=ATVPDKIKX0DER/profile=3917953989967300/period=2026-05-11_2026-05-17
```

### 5.5 Retention policy

为保护 Azure SQL free quota，必须设置保留策略：

```text
raw Amazon / Ads reports: 180 days
runtime/sampling manifests: 180 days
analysis_reports JSON/XLSX: 365 days
report_delivery packs: 365 days
send_result: 365 days
ingestion/debug previews: 30-90 days
```

第一版可先只写 `expires_at`，清理脚本后续实现：

```powershell
python scripts/prune_pipeline_artifacts.py --dry-run
python scripts/prune_pipeline_artifacts.py --execute
```

### 5.6 为什么不直接把 XLSX / raw file 当业务表

artifact store 只是文件持久化层，不参与业务口径计算。业务计算仍以 normalized tables 为准。

原则：

```text
normalized tables = 业务事实
pipeline_artifact_store = 文件缓存 / 审计证据 / job 间交接
```

---

## 6. 自动化 wrapper 设计

为了让现有脚本不用大改，第一版引入 wrapper：

```text
scripts/run_automation_stage.py
```

职责：

```text
1. 根据 stage/plan/report 参数，从 pipeline_artifact_store restore 必要文件到本地 runtime/reports。
2. 调用现有 CLI，例如 run_manual_refresh_plan.py / generate_*_report.py / send_report_email.py。
3. 执行完成后，把本阶段生成或更新的文件 upsert 到 pipeline_artifact_store。
4. 输出 stage_result.json，并用 exit code 表示成功/失败。
```

示例：

```powershell
python scripts/run_automation_stage.py --stage data_download --plan core_rolling --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_automation_stage.py --stage data_download --plan core_rolling --phase collect --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_automation_stage.py --stage data_ingestion --plan core_rolling --phase ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_automation_stage.py --stage report_delivery --report weekly_ads_optimization --week-start auto --audience ads_operator --execute
```

后续可再拆分为更语义化脚本：

```text
run_data_download_workflow.py
run_data_ingestion_workflow.py
run_report_delivery_workflow.py
```

---

## 7. 三阶段设计

## 7.1 Stage 1: 数据下载 / Data download

目标：提交和收集 Amazon 报表，不写 normalized business tables。

包含：

```text
submit -> persist manifest -> collect -> persist raw files
```

核心源继续使用：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase collect --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
```

Azure Jobs 实际调用 wrapper，wrapper 内部调用上述命令。

建议 jobs：

| Job name | Trigger v1 | Command wrapper | 说明 |
|---|---|---|---|
| `sdp-core-rolling-submit` | Scheduled every 2 days | `run_automation_stage.py --stage data_download --plan core_rolling --phase submit` | 提交核心数据请求并保存 manifest。 |
| `sdp-core-rolling-collect-1` | submit 后约 1h | `--phase collect` | restore manifest，收集 ready raw reports，保存 raw。 |
| `sdp-core-rolling-collect-2` | submit 后约 4h | `--phase collect` | 再次收集 pending 后完成的 reports。 |
| `sdp-weekly-full-submit` | Weekly | `--plan weekly_full --phase submit` | 每周提交慢源和财务相关请求。 |
| `sdp-weekly-full-collect-1` | Weekly + 1h | `--plan weekly_full --phase collect` | 第一次收集 weekly full raw reports。 |
| `sdp-weekly-full-collect-2` | Weekly + 4h | 同上 | 第二次收集。 |

---

## 7.2 Stage 2: 数据入库 / Data ingestion

目标：从 artifact store restore raw files，再 upsert 到 Azure SQL normalized tables，并运行覆盖审计。

包含：

```text
restore raw files -> ingest -> audit -> persist audit artifacts
```

核心命令仍是：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase audit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --target-start-date 2026-03-01 --execute
```

入库安全规则：

1. normalized 表继续采用 upsert 覆盖当前版本，不做多版本共存。
2. 自动化 jobs 不绕过 schema guard。
3. `requires_review=True` 时 job 应 exit non-zero 或输出 failure marker，不继续报表发送。
4. Orders ingestion 如再次触发 privacy/schema review guard，应作为 warning/failure 处理，不允许静默忽略。
5. audit 不要求所有源覆盖到今天，只要求 stable cutoff 窗口可用。

---

## 7.3 Stage 3: 数据报表与发送 / Reporting & delivery

目标：生成三类管理报表、生成双语邮件包，并在 send guard 允许时通过 SMTP 发送。

包含：

```text
generate report -> persist JSON/XLSX -> generate delivery pack -> persist pack -> send email -> persist send_result
```

三类报表：

```text
weekly_business_review
weekly_ads_optimization
monthly_financial_close
```

建议 wrapper：

```powershell
python scripts/run_report_delivery_workflow.py --report weekly_business_review --week-start auto --audience operations --execute
python scripts/run_report_delivery_workflow.py --report weekly_ads_optimization --week-start auto --audience ads_operator --execute
python scripts/run_report_delivery_workflow.py --report monthly_financial_close --month previous --audience shareholders --execute
```

发送规则保持不变：

```text
send_report_email.py 必须显式 --execute 才真实发送。
收件人来自 report_email_recipient_config。
needs_review / no_data / no_ads_data 默认不发送。
partial 报表按 audience guard 控制。
所有报告 presentation 层中英文双语。
```

---

## 8. 网络和防火墙 v1

公司初期采用低成本简化方案：

```text
Azure SQL firewall: create start IP = 0.0.0.0, end IP = 0.0.0.0 rule
```

该规则对应 Azure SQL 的 “Allow Azure services and resources to access this server”。它不是允许任意公网 IP，但它允许来自 Azure 内部服务的连接尝试。安全边界主要依赖：

```text
1. SQL 用户名/密码强度。
2. 最小权限 SQL 用户。
3. secrets 只放 Azure Job secrets / GitHub Actions secrets。
4. 不把连接串写进 Docker image 或代码库。
5. 后续有预算后再迁移到 fixed outbound IP / Private Endpoint。
```

本地开发仍可临时添加家庭公网 IP；自动化日常运行不再依赖本地 IP。

---

## 9. GitHub Actions 分工

GitHub Actions 不作为业务调度器，而作为 CI/CD：

```text
1. ruff / pytest / compileall
2. build Docker image
3. push image to GHCR
4. update Azure Container Apps Jobs image / command / env
5. optionally trigger manual smoke-test job
```

业务定时运行由 Azure Container Apps Jobs 负责。

---

## 10. 上线顺序

### Phase A: local + DB artifact store implementation

1. 新增 `pipeline_artifact_store` 设计与 migration。
2. 实现 artifact repository 和 save/restore helper。
3. 在本地模拟：save local report files -> delete local -> restore -> send/generate。

### Phase B: manual-triggered Azure Jobs

1. 创建 Container Apps Environment。
2. 使用 GHCR image。
3. 配置 Azure Job secrets。
4. 创建 manual jobs，不启用 schedule。
5. 手动触发 health check、data download、data ingestion、report delivery。

### Phase C: scheduled data refresh only

启用 submit / collect / ingest / audit schedule，但报告发送仍手动。

### Phase D: scheduled report generation without broad send

只发给 `feng@cuidena.cn`，连续两周确认。

### Phase E: scheduled send to DB recipients

恢复默认 DB recipients 三人发送。

---

## 11. 未来迁移触发条件

如出现以下任一情况，应重新评估 Azure Files / Blob / fixed outbound IP：

```text
Azure SQL free storage approaching 20GB
artifact table 单月增长超过 1GB
raw reports 保留超过 12 个月且查询变慢
XLSX/附件大幅增多
需要更严格安全审计
需要外部会计长期下载历史附件
需要多人共享文件而不经过数据库导出
```

迁移方向：

```text
pipeline_artifact_store 保留 metadata + hash + URI
文件内容迁移到 Azure Blob or Azure Files
Azure SQL 只存 normalized data / metadata
```

---

## 12. v1 implementation delivered in this change

新增代码：

```text
sql/migrations/014_create_pipeline_artifact_store.sql
src/seller_data_pipeline/db/repositories/pipeline_artifact_repo.py
src/seller_data_pipeline/services/pipeline_artifact_service.py
src/seller_data_pipeline/services/automation_schedule_service.py
scripts/manage_pipeline_artifacts.py
scripts/run_automation_stage.py
```

注意：`014_create_pipeline_artifact_store.sql` 执行成功并导出 live schema 前，不能更新 `docs/database/database_current_schema_spec.md`。

当前 wrapper 仍是 local/manual-trigger first，Azure Container Apps Jobs 资源尚未创建。
