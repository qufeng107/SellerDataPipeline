# Azure Container Apps Jobs Setup Checklist

> 更新时间：2026-05-25  
> 文档定位：记录 SellerDataPipeline 在 Azure Container Apps Jobs 上的 free-first 部署步骤、已验证状态、环境变量/secrets、以及如何高效复制/创建多个 jobs。  
> 相关文档：`docs/operations/azure_container_apps_jobs_workflow.md`, `docs/features/feature_automation_jobs_workflow.md`, `docs/adr/ADR-012-zero-paid-automation-storage-profile.md`

---

## 0. 当前真实进展

截至 2026-05-25，已完成：

```text
1. Azure SQL Networking 已勾选 Allow Azure services and resources to access this server。
2. GHCR package 已创建：ghcr.io/qufeng107/seller-data-pipeline。
3. GHCR 分支 tag 策略已修订：
   dev  -> :dev
   main -> :latest and :main
   all  -> :<git-sha>
4. Azure Container Apps Environment 已创建：
   sdp-containerapps-env
5. Log Analytics workspace 已由 Azure Portal 创建：
   workspacecergamazonopsb210
6. smoke job 已创建并成功：
   sdp-smoke-dev
7. 第一条业务 job 已创建并成功：
   sdp-weekly-submit-dev
```

`sdp-weekly-submit-dev` 真实成功证据：

```text
latest successful execution duration: about 1 min 35 sec
weekly_window=stats=2026-05-16..2026-05-22 request=2026-05-13..2026-05-22
Azure SQL connection warm-up succeeded after retries
SP-API backfill submitted total=1 for Sales & Traffic
SP-API backfill submitted total=1 for Orders
SP-API inventory snapshot submitted
Amazon Ads backfill submitted total=5
Automation stage workflow=weekly phase=submit mode=execute commands=4 failed=0
artifact_save scanned=8 saved=8 skipped=0
```

已知旧失败可忽略：

```text
python: can't open file '/app/scripts/run_automation_stage.py --workflow ...'
SyntaxError: invalid syntax
```

原因是 Azure Portal 的 `Command override` / `Arguments override` 传参方式错误，已修正，见第 5 节。

---

## 1. Free-first profile

第一版自动化采用：

```text
Azure Container Apps Jobs consumption plan
+ GitHub Container Registry image
+ Azure SQL free database
+ Azure SQL pipeline_artifact_store
+ SMTP email delivery
```

第一版暂不使用：

```text
Azure Files
Azure Blob Storage
Azure Container Registry
NAT Gateway / fixed outbound IP
Private Endpoint
Key Vault
```

---

## 2. Git branch / image tag strategy

```text
dev  branch -> GHCR image tag :dev
main branch -> GHCR image tags :latest and :main
all branches -> immutable tag :<git-sha>
```

当前 GHCR image：

```text
ghcr.io/qufeng107/seller-data-pipeline:dev
```

规则：

1. `dev` 用于云端手动 smoke test 和 manual dev jobs。
2. `main` 才用于正式 jobs。
3. `dev` 不推送 `latest`，避免开发镜像覆盖正式 job。
4. 第一阶段先手动创建 Azure jobs 并手动触发；等稳定后，再增加 main-only deploy workflow。

---

## 3. Azure SQL firewall

当前 v1 使用：

```text
Azure SQL Server -> Networking -> Exceptions
Allow Azure services and resources to access this server = checked
```

该选项用于允许 Azure 内部托管服务连接 SQL Server。v1 不做 NAT Gateway / Private Endpoint。

---

## 4. 已创建 Azure resources

| Resource | Type | Status | Notes |
|---|---|---|---|
| `sdp-containerapps-env` | Container Apps Environment | Created | West US 2 |
| `workspacecergamazonopsb210` | Log Analytics workspace | Created | Azure Portal 自动创建，注意控制日志量 |
| `sdp-smoke-dev` | Container App Job | Succeeded | command: `python --version` |
| `sdp-weekly-submit-dev` | Container App Job | Succeeded | weekly submit stage 已真实提交请求并保存 artifact |

---

## 5. Portal command/args rule

Azure Portal 的 `Arguments override` 可能会把整行参数当成一个参数传给 command。因此，业务 jobs 统一使用 shell 方式。

正确写法：

```text
Command override:
/bin/sh

Arguments override:
-c, python scripts/run_automation_stage.py --workflow weekly --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
```

不要使用：

```text
Command override:
python

Arguments override:
scripts/run_automation_stage.py --workflow weekly ...
```

否则 Azure 会把整行当作 Python 文件名，报：

```text
python: can't open file '/app/scripts/run_automation_stage.py --workflow ...'
```

也不要使用：

```text
Command override:
python

Arguments override:
-c, python scripts/run_automation_stage.py ...
```

否则会变成 `python -c "python scripts/..."`，报：

```text
SyntaxError: invalid syntax
```

---

## 6. Environment variables

### 6.1 Plain environment variables

这些可以明文配置到每个 job：

```env
APP_ENV=azure
LOG_LEVEL=INFO

AZURE_SQL_SERVER=amazon-ops-sql.database.windows.net
AZURE_SQL_DATABASE=amazon_ops
AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server
AZURE_SQL_AUTH_MODE=sql_password
AZURE_SQL_ENCRYPT=yes
AZURE_SQL_TRUST_SERVER_CERTIFICATE=no
AZURE_SQL_CONNECTION_TIMEOUT=30
AZURE_SQL_CONNECT_MAX_ATTEMPTS=6
AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS=5
AZURE_SQL_CONNECT_RETRY_BACKOFF=1.8

AMAZON_REGION=NA
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
AMAZON_SP_API_ENDPOINT=https://sellingpartnerapi-na.amazon.com
AMAZON_LWA_TOKEN_URL=https://api.amazon.com/auth/o2/token
AMAZON_SP_API_USER_AGENT=SellerDataPipeline/0.1.0

AMAZON_ADS_REGION=NA
AMAZON_ADS_API_ENDPOINT=https://advertising-api.amazon.com
AMAZON_ADS_PROFILE_ID=3917953989967300
AMAZON_ADS_USER_AGENT=SellerDataPipeline/0.1.0

LOCAL_SAMPLING_ROOT=runtime/sampling
RAW_REPORTS_ROOT=reports/raw
```

Report delivery jobs 还需要：

```env
REPORT_EMAIL_SMTP_HOST=smtp.exmail.qq.com
REPORT_EMAIL_SMTP_PORT=465
REPORT_EMAIL_SMTP_SECURITY=ssl
REPORT_EMAIL_FROM=feng@cuidena.cn
REPORT_EMAIL_FROM_NAME=CuideNA Reports
REPORT_EMAIL_REPLY_TO=feng@cuidena.cn
REPORT_EMAIL_SMTP_TIMEOUT_SECONDS=30
REPORT_EMAIL_SMTP_MAX_RETRIES=2
```

### 6.2 Secrets

每个需要访问 SQL/Amazon 的 job 都需要：

```text
azure-sql-username
azure-sql-password

amazon-lwa-client-id
amazon-lwa-client-secret
amazon-sp-api-refresh-token

amazon-ads-client-id
amazon-ads-client-secret
amazon-ads-refresh-token
```

对应 environment variable secret references：

```text
AZURE_SQL_USERNAME -> secretref:azure-sql-username
AZURE_SQL_PASSWORD -> secretref:azure-sql-password

AMAZON_LWA_CLIENT_ID -> secretref:amazon-lwa-client-id
AMAZON_LWA_CLIENT_SECRET -> secretref:amazon-lwa-client-secret
AMAZON_SP_API_REFRESH_TOKEN -> secretref:amazon-sp-api-refresh-token

AMAZON_ADS_CLIENT_ID -> secretref:amazon-ads-client-id
AMAZON_ADS_CLIENT_SECRET -> secretref:amazon-ads-client-secret
AMAZON_ADS_REFRESH_TOKEN -> secretref:amazon-ads-refresh-token
```

Report delivery jobs 还需要：

```text
report-email-smtp-username
report-email-smtp-password

REPORT_EMAIL_SMTP_USERNAME -> secretref:report-email-smtp-username
REPORT_EMAIL_SMTP_PASSWORD -> secretref:report-email-smtp-password
```

---

## 7. Job definitions

### 7.1 `sdp-smoke-dev`

Purpose: verify image pull and container startup.

```text
Image: ghcr.io/qufeng107/seller-data-pipeline:dev
Command: python
Arguments: --version
Trigger: Manual
Status: succeeded
```

### 7.2 `sdp-weekly-submit-dev`

Purpose: submit weekly report requests and save request manifests.

```text
Image: ghcr.io/qufeng107/seller-data-pipeline:dev
Command: /bin/sh
Arguments:
-c, python scripts/run_automation_stage.py --workflow weekly --phase submit --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute
Trigger: Manual
Status: succeeded
```

### 7.3 Next job: `sdp-weekly-collect-ingest-dev`

Purpose: restore manifests, collect ready reports, ingest normalized tables, audit, save artifacts.

```text
Image: ghcr.io/qufeng107/seller-data-pipeline:dev
Command: /bin/sh
Arguments:
-c, python scripts/run_automation_stage.py --workflow weekly --phase collect_ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute --continue-on-error
Trigger: Manual
```

Use the same SQL/Amazon env vars and secrets as `sdp-weekly-submit-dev`. SMTP is not needed.

### 7.4 Next job: `sdp-weekly-report-delivery-dev`

Purpose: generate WBR + WAOR, create delivery packs, send test emails.

```text
Image: ghcr.io/qufeng107/seller-data-pipeline:dev
Command: /bin/sh
Arguments:
-c, python scripts/run_automation_stage.py --workflow weekly --phase report_delivery --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute --send-email --email-to feng@cuidena.cn
Trigger: Manual
```

Use SQL/Amazon env vars and secrets plus SMTP env vars/secrets.

---

## 8. Efficient job creation: prefer Azure CLI over Portal copying

Azure Portal has no reliable “clone this job and change only arguments” workflow for this project. Manually re-entering env vars/secrets for every job is error-prone.

Recommended approach:

```text
1. Use Portal only for first smoke job and first weekly submit job.
2. Use Azure CLI / Cloud Shell for subsequent jobs.
3. Keep shared env vars and secret names in this checklist.
4. Create/update jobs from repeated CLI templates.
```

Recommended rollout model:

```text
Phase A: dev branch -> GHCR :dev -> manual dev jobs
  - create and run sdp-weekly-collect-ingest-dev
  - create and run sdp-weekly-report-delivery-dev
  - then create and run monthly dev jobs

Phase B: when dev jobs are stable -> merge to main
  - main branch builds GHCR :main and :latest
  - official jobs should use :main or :latest, not :dev

Phase C: official jobs still start as manual/safe-run first
  - run official main-image jobs manually once or twice
  - then enable schedule for data refresh/report delivery
  - broad DB-recipient email send only after stable validation
```

### 8.1 Shared variables

```bash
RG="rg-amazon-ops"
ENV_NAME="sdp-containerapps-env"
IMAGE="ghcr.io/qufeng107/seller-data-pipeline:dev"
CPU="0.5"
MEMORY="1.0Gi"
```

### 8.2 Create `sdp-weekly-collect-ingest-dev`

```bash
az containerapp job create   --name sdp-weekly-collect-ingest-dev   --resource-group "$RG"   --environment "$ENV_NAME"   --trigger-type Manual   --replica-timeout 3600   --replica-retry-limit 0   --parallelism 1   --replica-completion-count 1   --image "$IMAGE"   --cpu "$CPU"   --memory "$MEMORY"   --command "/bin/sh"   --args "-c" "python scripts/run_automation_stage.py --workflow weekly --phase collect_ingest --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute --continue-on-error"
```

Then set secrets and env vars using the same names as `sdp-weekly-submit-dev`.

### 8.3 Create `sdp-weekly-report-delivery-dev`

```bash
az containerapp job create   --name sdp-weekly-report-delivery-dev   --resource-group "$RG"   --environment "$ENV_NAME"   --trigger-type Manual   --replica-timeout 3600   --replica-retry-limit 0   --parallelism 1   --replica-completion-count 1   --image "$IMAGE"   --cpu "$CPU"   --memory "$MEMORY"   --command "/bin/sh"   --args "-c" "python scripts/run_automation_stage.py --workflow weekly --phase report_delivery --marketplace-id ATVPDKIKX0DER --profile-id 3917953989967300 --execute --send-email --email-to feng@cuidena.cn"
```

### 8.4 Set secret references

After creating a job, set secret references in env vars:

```bash
az containerapp job update   --name sdp-weekly-collect-ingest-dev   --resource-group "$RG"   --set-env-vars     AZURE_SQL_USERNAME=secretref:azure-sql-username     AZURE_SQL_PASSWORD=secretref:azure-sql-password     AMAZON_LWA_CLIENT_ID=secretref:amazon-lwa-client-id     AMAZON_LWA_CLIENT_SECRET=secretref:amazon-lwa-client-secret     AMAZON_SP_API_REFRESH_TOKEN=secretref:amazon-sp-api-refresh-token     AMAZON_ADS_CLIENT_ID=secretref:amazon-ads-client-id     AMAZON_ADS_CLIENT_SECRET=secretref:amazon-ads-client-secret     AMAZON_ADS_REFRESH_TOKEN=secretref:amazon-ads-refresh-token
```

Report delivery job also needs:

```bash
az containerapp job update   --name sdp-weekly-report-delivery-dev   --resource-group "$RG"   --set-env-vars     REPORT_EMAIL_SMTP_USERNAME=secretref:report-email-smtp-username     REPORT_EMAIL_SMTP_PASSWORD=secretref:report-email-smtp-password
```

### 8.5 Start and inspect jobs

```bash
az containerapp job start   --name sdp-weekly-collect-ingest-dev   --resource-group "$RG"

az containerapp job execution list   --name sdp-weekly-collect-ingest-dev   --resource-group "$RG"
```

---

## 9. Log queries

Console logs:

```kusto
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(24h)
| where ContainerGroupName_s contains "sdp-weekly"
   or ContainerName_s contains "sdp-weekly"
   or Log_s contains "Automation stage"
| project TimeGenerated, ContainerGroupName_s, ContainerName_s, Log_s
| order by TimeGenerated desc
```

System logs:

```kusto
ContainerAppSystemLogs_CL
| where TimeGenerated > ago(24h)
| where ContainerGroupName_s contains "sdp-weekly"
   or Log_s contains "sdp-weekly"
| project TimeGenerated, ContainerGroupName_s, Type_s, Reason_s, Log_s
| order by TimeGenerated desc
```

---

## 10. SQL artifact verification

After `submit` succeeds, verify artifacts using the live schema column names.

Important field names:

```text
artifact_scope       workflow/period scope key; do not use scope
content_size_bytes   original uncompressed file size; do not use original_size_bytes
compressed_size_bytes gzip compressed size stored in SQL
```

Exact scope check:

```sql
SELECT TOP 50
    artifact_scope,
    artifact_type,
    relative_path,
    content_size_bytes AS original_size_bytes,
    compressed_size_bytes,
    created_at,
    expires_at
FROM dbo.pipeline_artifact_store
WHERE artifact_scope = 'weekly:ATVPDKIKX0DER:3917953989967300:2026-05-16_2026-05-22'
  AND is_deleted = 0
ORDER BY created_at DESC;
```

Summary:

```sql
SELECT
    artifact_scope,
    artifact_type,
    COUNT(*) AS artifact_count,
    SUM(content_size_bytes) AS total_original_bytes,
    SUM(compressed_size_bytes) AS total_compressed_bytes,
    MAX(created_at) AS latest_created_at
FROM dbo.pipeline_artifact_store
WHERE artifact_scope LIKE 'weekly:ATVPDKIKX0DER:3917953989967300:%'
  AND is_deleted = 0
GROUP BY artifact_scope, artifact_type
ORDER BY latest_created_at DESC;
```

---

## 11. Next steps

1. Confirm `pipeline_artifact_store` contains submit manifests from Azure job.
2. Create `sdp-weekly-collect-ingest-dev`.
3. Run collect/ingest once; if reports are pending, rerun once after 30 minutes.
4. Create `sdp-weekly-report-delivery-dev`.
5. Send only to `feng@cuidena.cn` using `--email-to`.
6. After three weekly dev jobs are stable, create monthly dev jobs.
7. After dev jobs are stable, add main-only deployment workflow to update official jobs.
