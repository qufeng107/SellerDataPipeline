# Azure Container Apps Jobs Workflow

> 更新时间：2026-05-25  
> 文档定位：定义 SellerDataPipeline 从手动流程迁移到 Azure Container Apps Jobs 的运行方案。本文是 operations runbook，不定义业务指标口径；业务口径见 `docs/features/`。

---


## 0. 当前落地清单

Azure Container Apps Jobs 已开始 manual dev rollout。开通和配置步骤见：

```text
docs/operations/azure_container_apps_jobs_setup_checklist.md
```

当前已完成：

```text
GHCR package: ghcr.io/qufeng107/seller-data-pipeline
dev image: ghcr.io/qufeng107/seller-data-pipeline:dev
Container Apps environment: sdp-containerapps-env
Log Analytics workspace: workspacecergamazonopsb210
sdp-smoke-dev: succeeded
sdp-weekly-submit-dev: succeeded
```

`sdp-weekly-submit-dev` 真实成功证据：

```text
weekly_window=stats=2026-05-16..2026-05-22 request=2026-05-13..2026-05-22
SP-API Sales & Traffic / Orders / Inventory requests submitted
Amazon Ads report requests submitted total=5
Automation stage workflow=weekly phase=submit mode=execute commands=4 failed=0
artifact_save scanned=8 saved=8 skipped=0
```

当前代码已支持：

```text
run_automation_stage.py --email-to feng@cuidena.cn
```

该参数只在 `report_delivery` 阶段透传到 `send_report_email.py --to ...`，用于云端 smoke test 时临时只发给自己；稳定后去掉该参数，恢复数据库收件人路由。

Portal command/args 规则已冻结：

```text
Command override = /bin/sh
Arguments override = -c, python scripts/run_automation_stage.py ...
```

下一步：创建 `sdp-weekly-collect-ingest-dev`，再创建 `sdp-weekly-report-delivery-dev`。

---

## 1. 总原则

自动化只调度已经人工验证过的 CLI，不改变数据口径。

当前三阶段：

```text
1. Data download：submit + collect raw reports
2. Data ingestion：ingest + audit
3. Reporting & delivery：generate reports + generate delivery pack + send email
```

2026-05-24 成本策略调整为：

```text
Azure Container Apps Jobs consumption plan
+ GitHub Container Registry image
+ Azure SQL free database
+ Azure SQL artifact store for cross-job files
+ SMTP email delivery
```

第一版不使用：

```text
Azure Files
Azure Blob Storage
Azure Container Registry
NAT Gateway
Private Endpoint
```

---

## 2. 需要理解的组件

| 组件 | 本项目用途 | v1 成本策略 |
|---|---|---|
| GitHub Actions | CI/CD：测试、构建镜像、推送 GHCR、更新 Azure Jobs | 继续使用现有 GitHub Actions 免费额度 |
| Docker image | 固化 Python 运行环境和脚本 | 由 GitHub Actions 构建 |
| GHCR | 存 Docker image | 优先使用 GitHub Container Registry，避免 ACR 基础资源 |
| Azure Container Apps Jobs | 云端手动/定时执行 CLI | 使用 consumption plan，小任务优先吃免费额度 |
| Azure SQL | normalized data + config + artifact store | 使用当前 free database |
| SMTP | 发送报告邮件 | 腾讯企业邮 `smtp.exmail.qq.com:465 ssl` |

---

## 3. Job 设计总览

### 3.1 Core rolling jobs

| Job | 建议触发 | 说明 |
|---|---|---|
| `sdp-core-rolling-submit` | 每 2 天 | 提交核心滚动数据请求，并持久化 request manifests。 |
| `sdp-core-rolling-collect-1` | submit 后约 1 小时 | 从 DB artifact store restore manifests，收集 ready raw reports，并持久化 raw files。 |
| `sdp-core-rolling-collect-2` | submit 后约 4 小时 | 再次收集 pending 后完成的 reports。 |
| `sdp-core-rolling-ingest` | collect-2 后 | restore raw files，入库核心滚动数据。 |
| `sdp-core-rolling-audit` | ingest 后 | 覆盖审计并持久化 audit artifacts。 |

### 3.2 Weekly full jobs

| Job | 建议触发 | 说明 |
|---|---|---|
| `sdp-weekly-full-submit` | 每周一次 | 提交慢源、财务、库存流水相关请求。 |
| `sdp-weekly-full-collect-1` | submit 后约 1 小时 | 收集 ready reports。 |
| `sdp-weekly-full-collect-2` | submit 后约 4 小时 | 再次收集。 |
| `sdp-weekly-full-ingest` | collect-2 后 | 入库 weekly full 数据。 |
| `sdp-weekly-full-audit` | ingest 后 | 周报/月报前审计。 |

### 3.3 Report-driven weekly jobs

周报周期固定为 Saturday-Friday。每周一调度时自动计算：

```text
stats window = 上上周六 .. 上周五
request window = 上上周三 .. 上周五
```

| Job | 建议触发 | 命令 | 说明 |
|---|---|---|---|
| `sdp-weekly-submit` | 周一 09:00 | `run_automation_stage.py --workflow weekly --phase submit --execute` | 提交 Sales & Traffic / Orders / Ads / Inventory 请求。 |
| `sdp-weekly-collect-ingest-1` | 周一 11:00 | `run_automation_stage.py --workflow weekly --phase collect_ingest --execute` | 第一次 collect + ingest + audit。 |
| `sdp-weekly-collect-ingest-2` | 周一 11:30 | 同上 | 唯一一次重试，仍未生成的源留作 partial/warning。 |
| `sdp-weekly-report-delivery` | 周一 12:00 | `run_automation_stage.py --workflow weekly --phase report_delivery --send-email --execute` | 生成 WBR + WAOR，生成邮件包并发送。 |

### 3.4 Report-driven monthly jobs

每月 3 日处理上一个自然月。

| Job | 建议触发 | 命令 | 说明 |
|---|---|---|---|
| `sdp-monthly-submit` | 每月 3 日 09:00 | `run_automation_stage.py --workflow monthly --phase submit --execute` | 提交/发现 Sales & Traffic / Orders / Ads / Settlement / FBA Reimbursements / Promotion-Coupon。 |
| `sdp-monthly-collect-ingest-1` | 每月 3 日 11:00 | `run_automation_stage.py --workflow monthly --phase collect_ingest --execute` | 第一次 collect + ingest + audit。 |
| `sdp-monthly-collect-ingest-2` | 每月 3 日 11:30 | 同上 | 唯一一次重试。 |
| `sdp-monthly-report-delivery` | 每月 3 日 12:00 | `run_automation_stage.py --workflow monthly --phase report_delivery --send-email --execute` | 生成 Monthly Financial Close 并发送。 |

---

## 4. Artifact persistence without Azure Files

Container Apps Job execution 结束后本地文件会消失。v1 不使用 Azure Files，因此必须把跨 job 所需文件存进 Azure SQL artifact store。

需要持久化：

```text
runtime/sampling
runtime/ingestion selected outputs
runtime/analysis_reports
runtime/report_delivery
reports/raw
```

不需要长期持久化：

```text
__pycache__
temporary extraction files
large debug previews after retention
local logs already emitted to job stdout/stderr
```

实现方式：

```text
1. Job start: restore required artifacts from dbo.pipeline_artifact_store to local runtime/reports.
2. Run existing CLI in local workspace.
3. Job finish: compress changed output files and upsert to dbo.pipeline_artifact_store.
4. Later jobs restore from DB instead of shared file mount.
```

这样现有脚本仍然使用相对路径：

```text
runtime/...
reports/raw/...
```

但跨 job 的文件交接由数据库完成。

---

## 5. Efficient Azure Job provisioning

Do not continue creating every job manually through Azure Portal. The first smoke and submit jobs were useful to validate Portal behavior, but future jobs should be created through Azure CLI / Cloud Shell so env vars and secret references are repeatable.

Recommended pattern:

```text
1. Portal only for smoke/debug.
2. Azure CLI for collect_ingest/report_delivery/monthly jobs.
3. Same GHCR image, same SQL/Amazon secrets.
4. Only command arguments differ by job.
5. Report delivery jobs additionally receive SMTP secrets.
```

Core reason: Azure Portal does not provide a reliable project-level clone workflow for copying the full job definition and only changing arguments. CLI templates reduce manual mistakes.

Example command pattern is maintained in:

```text
docs/operations/azure_container_apps_jobs_setup_checklist.md
```

Important argument rule:

```text
--command "/bin/sh"
--args "-c" "python scripts/run_automation_stage.py ..."
```


## 5. 推荐命令模型

第一版建议新增 wrapper：

```powershell
python scripts/run_automation_stage.py --stage data_download --plan core_rolling --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_automation_stage.py --stage data_download --plan core_rolling --phase collect --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_automation_stage.py --stage data_ingestion --plan core_rolling --phase ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
python scripts/run_automation_stage.py --stage data_ingestion --plan core_rolling --phase audit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --target-start-date 2026-03-01 --execute
python scripts/run_automation_stage.py --stage report_delivery --report weekly_ads_optimization --week-start auto --audience ads_operator --execute
```

wrapper 内部复用现有命令：

```powershell
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase submit ... --execute
python scripts/run_manual_refresh_plan.py --plan core_rolling --phase collect ... --execute
python scripts/generate_weekly_ads_optimization_report.py ... --dry-run
python scripts/generate_report_delivery_pack.py ... --dry-run
python scripts/send_report_email.py ... --execute
```

---

## 6. Secrets / 环境变量

Azure Job 需要注入与本地一致的环境变量：

```text
Azure SQL connection
Amazon SP-API credentials
Amazon Ads API credentials
REPORT_EMAIL_SMTP_HOST
REPORT_EMAIL_SMTP_PORT
REPORT_EMAIL_SMTP_SECURITY
REPORT_EMAIL_SMTP_USERNAME
REPORT_EMAIL_SMTP_PASSWORD
REPORT_EMAIL_FROM
REPORT_EMAIL_FROM_NAME
REPORT_EMAIL_REPLY_TO
```

禁止：

```text
把 secrets 写入 Git、Docker image、SQL 表或 runtime output。
```

---

## 7. 网络要求

Azure Jobs 需要访问：

```text
Azure SQL
Amazon SP-API
Amazon Ads API
Tencent Exmail SMTP
GHCR image registry
```

v1 低成本方案：

```text
Azure SQL firewall rule start IP = 0.0.0.0, end IP = 0.0.0.0
```

这对应 Azure SQL 的 “Allow Azure services and resources to access this server”。它简化了 Container Apps Jobs 访问 Azure SQL 的问题，但不是严格私网隔离。

安全最低要求：

```text
1. Azure SQL 用户必须最小权限。
2. SQL 密码、SP-API、Ads API、SMTP 密码只能放在 Azure Job secrets / GitHub secrets。
3. 不允许把 secrets 写入 artifact store。
4. 本地 IP rule 仍按需临时添加，自动化日常运行不依赖家庭公网 IP。
```

未来增强：

```text
Container Apps workload profile + VNet + NAT Gateway fixed outbound IP
或 Private Endpoint
```

---

## 8. CI/CD 分工

GitHub Actions：

```text
1. ruff check src tests scripts
2. PYTHONPATH=src pytest tests/unit -q
3. python -m compileall -q scripts src tests
4. build Docker image
5. push image to GHCR
6. update Azure Container Apps Jobs
```

Azure Container Apps Jobs：

```text
1. submit
2. collect
3. ingest
4. audit
5. report generation
6. delivery pack generation
7. SMTP send
```

不要让 GitHub Actions 直接承担长期业务 schedule。

---

## 9. 上线顺序

### 9.1 Local DB artifact store test

先在本地实现并测试：

```text
save local files to pipeline_artifact_store
restore files to empty runtime/reports
run report delivery from restored files
prune expired artifacts dry-run
```

### 9.2 Manual-triggered Azure Jobs

先创建 jobs，但不启用 schedule。

当前 Azure rollout 采用 dev-first / manual-first：

```text
dev branch -> GHCR :dev -> manual dev jobs -> validate logs/data/email
main branch -> GHCR :main/:latest -> official jobs -> manual validation -> schedule
```

顺序：

```text
health check
weekly submit
weekly collect_ingest
weekly report delivery with --email-to feng@cuidena.cn
monthly submit
monthly collect_ingest
monthly report delivery with --email-to feng@cuidena.cn
main-image official jobs manual validation
scheduled refresh/report delivery
```

### 9.3 Scheduled refresh only

启用数据刷新 schedule，但报告发送仍手动。

目标：连续两轮 core_rolling 和一轮 weekly_full 成功。

### 9.4 Scheduled report generation without broad send

启用报表生成和 delivery pack，但只发给 `feng@cuidena.cn`。

### 9.5 Scheduled send

确认 2 周稳定后，使用 DB recipients 默认三人发送。

---

## 10. 排错检查

### 10.1 collect 找不到 manifest

检查：

```text
pipeline_artifact_store 是否有 sp_report_request_manifest / ads_report_request_manifest
restore step 是否成功写回 runtime/sampling
artifact_scope 是否和 plan/marketplace/profile 匹配
```

### 10.2 ingest 找不到 raw file

检查：

```text
collect step 是否保存 sp_raw_report / ads_raw_report
restore step 是否恢复到 reports/raw/...
raw report retention 是否过期
```

### 10.3 report delivery 找不到 XLSX

检查：

```text
generate report step 是否保存 analysis_report_xlsx
run_report_delivery_workflow 是否使用同一 period key
```

### 10.4 SQL free quota 风险

检查：

```sql
SELECT
    artifact_type,
    COUNT(*) AS row_count,
    SUM(compressed_size_bytes) AS compressed_bytes
FROM dbo.pipeline_artifact_store
WHERE is_deleted = 0
GROUP BY artifact_type
ORDER BY compressed_bytes DESC;
```

如果 artifact store 增长过快，优先缩短 raw/debug retention。

---

## 10. Current local wrapper commands

执行 migration 014 后，先在本地用以下命令验证：

```powershell
python scripts/run_sql_migration.py --file sql/migrations/014_create_pipeline_artifact_store.sql --dry-run --show-batches
python scripts/run_sql_migration.py --file sql/migrations/014_create_pipeline_artifact_store.sql

python scripts/run_automation_stage.py --workflow weekly --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --reference-date 2026-05-25 --execute
python scripts/run_automation_stage.py --workflow weekly --phase collect_ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --reference-date 2026-05-25 --execute
python scripts/run_automation_stage.py --workflow weekly --phase report_delivery --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --reference-date 2026-05-25 --send-email --execute
```

如果只是检查命令和 artifact restore/save 计划，不加 `--execute`。
