# Azure Container Apps Jobs Setup Checklist

> 更新时间：2026-05-24  
> 文档定位：从“本地自动化 wrapper 已跑通”迁移到 Azure Container Apps Jobs 的开通和配置清单。本文优先采用 free-first profile：GHCR + Azure SQL artifact store，不使用 Azure Files / ACR。

---

## 1. 目标架构

```text
GitHub Actions
  -> build Docker image
  -> push image to GHCR
  -> later: update Azure Container Apps Jobs image/command

Azure Container Apps Jobs
  -> run scripts/run_automation_stage.py
  -> short-lived job execution, then exit

Azure SQL free database
  -> normalized data
  -> report_email_recipient_config
  -> pipeline_artifact_store

Tencent Exmail SMTP
  -> send report emails
```

第一阶段只创建 **manual-triggered jobs**，手动从 Azure Portal/CLI 触发验证；验证稳定后再启用 scheduled jobs。

---

## 2. Azure 侧需要开通什么

### 2.1 Resource group

可复用现有资源组，也可新建：

```text
sdp-rg
```

用途：统一放 Container Apps Environment / Jobs / Log Analytics 等资源。

### 2.2 Azure Container Apps Environment

需要新建一个 Container Apps Environment，例如：

```text
sdp-containerapps-env
```

建议：

```text
Plan: Consumption
Region: 尽量和 Azure SQL 同区域，减少网络延迟
```

Azure Portal 路径：

```text
Create a resource
-> Container Apps Environment
```

也可以在创建第一个 Container Apps Job 时让 Azure Portal 引导创建 environment。

### 2.3 Azure Container Apps Jobs

第一阶段建议创建 6 个 manual-triggered jobs：

```text
sdp-weekly-submit
sdp-weekly-collect-ingest
sdp-weekly-report-delivery
sdp-monthly-submit
sdp-monthly-collect-ingest
sdp-monthly-report-delivery
```

先不创建 schedule。每个 job 使用同一个 image，只是 command 不同。

### 2.4 Azure SQL firewall

free-first v1 使用 Azure SQL server firewall：

```text
Allow Azure services and resources to access this server = Yes
```

等价于 server-level firewall rule：

```text
Start IP = 0.0.0.0
End IP   = 0.0.0.0
```

这允许 Azure 内部托管服务尝试连接 SQL。安全边界依赖：

```text
1. SQL 用户名/密码强度
2. 最小权限 SQL 用户
3. secrets 不进入 Git / Docker image / 数据库表
```

---

## 3. GitHub / GHCR 侧需要做什么

### 3.1 启用 GitHub Packages / GHCR

本项目已新增：

```text
.github/workflows/build-ghcr-image.yml
```

触发方式：

```text
GitHub -> Actions -> Build GHCR image -> Run workflow
```

成功后会推送：

```text
ghcr.io/<owner>/seller-data-pipeline:<git-sha>
ghcr.io/<owner>/seller-data-pipeline:latest
```

注意：GHCR image 名称会自动转小写。

### 3.2 Azure 拉取 GHCR image 的方式

有两种方式：

#### 方式 A：把 GHCR package 设为 public

优点：Azure Job 拉镜像最简单，不需要 registry password。

缺点：镜像可公开拉取，不应把 secrets 放进 image。当前 Dockerfile 不复制 `.env` 和 `runtime/`，所以可以接受。

#### 方式 B：保持 GHCR package private

需要创建 GitHub PAT：

```text
GitHub -> Settings -> Developer settings -> Personal access tokens
```

需要权限：

```text
read:packages
```

然后在 Azure Container Apps Job 里配置 registry credentials：

```text
Registry server: ghcr.io
Username: GitHub username
Password: GitHub PAT with read:packages
```

---

## 4. Container Apps Job 环境变量和 secrets

建议分类：

```text
non-secret env vars: 可明文设置在 job environment variables
secret values: 设置为 Container Apps secrets，再用 env var 引用 secret
```

### 4.1 非敏感环境变量

| 变量 | 示例 | 从哪里拿 |
|---|---|---|
| `APP_ENV` | `azure` | 固定值 |
| `LOG_LEVEL` | `INFO` | 固定值 |
| `AMAZON_REGION` | `NA` | 当前项目 `.env` |
| `AMAZON_MARKETPLACE_ID` | `ATVPDKIKX0DER` | Seller Central / 当前 `.env` |
| `AMAZON_SP_API_ENDPOINT` | `https://sellingpartnerapi-na.amazon.com` | 当前 `.env` |
| `AMAZON_LWA_TOKEN_URL` | `https://api.amazon.com/auth/o2/token` | 当前 `.env` |
| `AMAZON_SP_API_USER_AGENT` | `SellerDataPipeline/0.1.0 (Language=Python/3.11)` | 当前 `.env` |
| `AMAZON_ADS_REGION` | `NA` | 当前 `.env` |
| `AMAZON_ADS_API_ENDPOINT` | `https://advertising-api.amazon.com` | 当前 `.env` |
| `AMAZON_ADS_PROFILE_ID` | `3917953989967300` | Ads profile discovery / 当前 `.env` |
| `AMAZON_ADS_USER_AGENT` | `SellerDataPipeline/0.1.0 (Language=Python/3.11)` | 当前 `.env` |
| `AZURE_SQL_SERVER` | `<server>.database.windows.net` | Azure SQL Server Overview |
| `AZURE_SQL_DATABASE` | `amazon_ops` | Azure SQL Database Overview |
| `AZURE_SQL_DRIVER` | `ODBC Driver 18 for SQL Server` | Dockerfile 已安装 |
| `AZURE_SQL_AUTH_MODE` | `sql_password` | v1 固定 SQL password |
| `AZURE_SQL_ENCRYPT` | `yes` | 固定值 |
| `AZURE_SQL_TRUST_SERVER_CERTIFICATE` | `no` | 固定值 |
| `AZURE_SQL_CONNECTION_TIMEOUT` | `30` | 当前 `.env` |
| `AZURE_SQL_CONNECT_MAX_ATTEMPTS` | `6` | 当前 `.env` |
| `AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS` | `5` | 当前 `.env` |
| `AZURE_SQL_CONNECT_RETRY_BACKOFF` | `1.8` | 当前 `.env` |
| `LOCAL_SAMPLING_ROOT` | `runtime/sampling` | 固定值 |
| `RAW_REPORTS_ROOT` | `reports/raw` | 固定值 |
| `REPORT_EMAIL_SMTP_HOST` | `smtp.exmail.qq.com` | 企业微信邮箱客户端设置 |
| `REPORT_EMAIL_SMTP_PORT` | `465` | 企业微信邮箱客户端设置 |
| `REPORT_EMAIL_SMTP_SECURITY` | `ssl` | 企业微信邮箱客户端设置 |
| `REPORT_EMAIL_FROM` | `feng@cuidena.cn` | 发信邮箱 |
| `REPORT_EMAIL_FROM_NAME` | `CuideNA Reports` | 自定义 |
| `REPORT_EMAIL_REPLY_TO` | `feng@cuidena.cn` | 自定义 |
| `REPORT_EMAIL_SMTP_TIMEOUT_SECONDS` | `30` | 当前 `.env` |
| `REPORT_EMAIL_SMTP_MAX_RETRIES` | `2` | 当前 `.env` |

### 4.2 Secret 环境变量

| 变量 | 从哪里拿 | 说明 |
|---|---|---|
| `AMAZON_LWA_CLIENT_ID` | Amazon Developer / 当前 `.env` | SP-API LWA client id |
| `AMAZON_LWA_CLIENT_SECRET` | Amazon Developer / 当前 `.env` | SP-API LWA secret |
| `AMAZON_SP_API_REFRESH_TOKEN` | SP-API 授权流程 / 当前 `.env` | SP-API refresh token |
| `AMAZON_ADS_CLIENT_ID` | Amazon Developer / 当前 `.env` | 可与 LWA client id 相同 |
| `AMAZON_ADS_CLIENT_SECRET` | Amazon Developer / 当前 `.env` | 可与 LWA secret 相同 |
| `AMAZON_ADS_REFRESH_TOKEN` | Ads API 授权流程 / 当前 `.env` | Ads refresh token |
| `AZURE_SQL_USERNAME` | Azure SQL / 当前 `.env` | 建议后续换最小权限用户 |
| `AZURE_SQL_PASSWORD` | Azure SQL / 当前 `.env` | 不写入镜像或数据库 |
| `REPORT_EMAIL_SMTP_USERNAME` | 企业微信邮箱 | `feng@cuidena.cn` |
| `REPORT_EMAIL_SMTP_PASSWORD` | 企业微信邮箱客户端专用密码 | 不要用普通密码；不要提交 Git |

---

## 5. Manual job command 设计

所有 job 使用同一个 image，命令不同。

### Weekly submit

```bash
python scripts/run_automation_stage.py \
  --workflow weekly \
  --phase submit \
  --marketplace-id ATVPDKIKX0DER \
  --profile-id 3917953989967300 \
  --execute
```

### Weekly collect + ingest

第一次：

```bash
python scripts/run_automation_stage.py \
  --workflow weekly \
  --phase collect_ingest \
  --marketplace-id ATVPDKIKX0DER \
  --profile-id 3917953989967300 \
  --execute \
  --continue-on-error
```

重试 job 使用同一命令。

### Weekly report + delivery

测试阶段只发给自己：

```bash
python scripts/run_automation_stage.py \
  --workflow weekly \
  --phase report_delivery \
  --marketplace-id ATVPDKIKX0DER \
  --profile-id 3917953989967300 \
  --execute \
  --send-email \
  --email-to feng@cuidena.cn
```

稳定后去掉 `--email-to`，走数据库收件人路由。

### Monthly submit

```bash
python scripts/run_automation_stage.py \
  --workflow monthly \
  --phase submit \
  --marketplace-id ATVPDKIKX0DER \
  --profile-id 3917953989967300 \
  --execute
```

### Monthly collect + ingest

```bash
python scripts/run_automation_stage.py \
  --workflow monthly \
  --phase collect_ingest \
  --marketplace-id ATVPDKIKX0DER \
  --profile-id 3917953989967300 \
  --execute \
  --continue-on-error
```

### Monthly report + delivery

```bash
python scripts/run_automation_stage.py \
  --workflow monthly \
  --phase report_delivery \
  --marketplace-id ATVPDKIKX0DER \
  --profile-id 3917953989967300 \
  --execute \
  --send-email \
  --email-to feng@cuidena.cn
```

---

## 6. Schedule 建议，等 manual job 验证后再启用

Azure Container Apps Jobs schedule 使用 5-field cron。注意选择统一时区；v1 建议直接按 UTC 配置，并在文档里换算本地时间。

建议 UTC 时间：

```text
weekly submit:          Monday 08:00 UTC
weekly collect_ingest1: Monday 10:00 UTC
weekly collect_ingest2: Monday 10:30 UTC
weekly report_delivery: Monday 11:00 UTC

monthly submit:          3rd day 08:00 UTC
monthly collect_ingest1: 3rd day 10:00 UTC
monthly collect_ingest2: 3rd day 10:30 UTC
monthly report_delivery: 3rd day 11:00 UTC
```

对应 cron：

```text
0 8 * * 1
0 10 * * 1
30 10 * * 1
0 11 * * 1

0 8 3 * *
0 10 3 * *
30 10 3 * *
0 11 3 * *
```

---

## 7. 第一轮验收顺序

1. 本地跑 `ruff / pytest / compileall`。
2. GitHub Actions 手动触发 `Build GHCR image`。
3. 在 GHCR 确认 image 已生成。
4. Azure Portal 创建 Container Apps Environment。
5. Azure SQL 开启 Allow Azure services。
6. 创建 `sdp-weekly-submit` manual job，填 env/secrets。
7. 手动 start job，查看 logs。
8. 创建并手动跑 collect_ingest job。
9. 创建并手动跑 report_delivery job，带 `--email-to feng@cuidena.cn`。
10. 收到邮件后再考虑启用 schedule。

