# Feature: Report Delivery / Email Pack

> 文档状态：Implemented v1.1  
> 负责人：AI + Feng  
> 更新时间：2026-05-23  
> 功能状态：v1 draft-pack implemented; v1.1 SMTP sending implemented  
> 相关功能：`docs/features/feature_monthly_financial_close_report.md`, `docs/features/feature_weekly_business_review.md`, `docs/features/feature_weekly_ads_optimization_report.md`  
> 相关 operations：`docs/operations/manual_refresh_plan_workflow.md`, `docs/operations/data_refresh_policy.md`  
> 相关原则：手动优先、先 dry-run 再 execute、不新增数据库表、不把敏感配置提交到代码库

---

## 1. 功能摘要

Report Delivery / Email Pack 是三类管理报表之后的统一交付层。它不重新计算业务指标，也不读取数据库，而是读取已经生成的报表 JSON，并找到对应 XLSX 附件，生成一份可人工复核的邮件交付包；后续再由发送脚本通过 SMTP 发送。

目标是用同一个通用功能支持三种模板：

```text
Monthly Financial Close Report -> 股东 / 会计 / 运营负责人月结邮件
Weekly Business Review -> CEO / 运营负责人周经营复盘邮件
Weekly Ads Optimization Report -> 广告操作者 / 运营负责人广告动作邮件
```

v1 已实现安全的“生成邮件草稿包”。v1.1 已实现 SMTP 真实发送：使用 Python 标准库 SMTP 客户端发送已经生成并人工复核过的 delivery pack；收件人按 report_type + audience 路由配置，不把 SMTP 密码提交到代码库。当前小团队阶段不新增收件人数据库表，默认使用 runtime 本地 JSON 配置，后续如需要多人管理/审计再升级为数据库表。

---

## 2. 设计目标

1. **一个通用 delivery 功能**：不要为三份报表各写一套发送流程。
2. **三种模板适配器**：按 `report_type` 自动选择 Monthly / WBR / WAOR 模板。
3. **JSON 作为邮件正文 source of truth**：邮件正文只从报表 JSON 提取，不反向解析 XLSX。
4. **XLSX 作为主要附件**：给股东、会计、运营人员人工查看；JSON 默认不对外发送。
5. **默认不发送**：第一阶段只生成 `email_subject.txt`、`email_body.html`、`email_body.txt`、`delivery_manifest.json`。
6. **真实发送必须显式 `--execute`**：避免误发。
7. **不新增数据库表 / migration**：delivery 结果先存 runtime 文件，不落库。
8. **敏感配置不入库**：SMTP 密码走环境变量；收件人列表走 `runtime/config/report_delivery_recipients.json` 或 CLI 参数。
9. **状态保护**：`needs_review` 报表默认不允许发送给股东/会计，除非显式 override。
10. **后续可接 Azure Jobs**：但当前仍以手动/半自动流程为主。

---

## 3. 功能边界

### 3.1 v1 包含

1. 读取单个报表 JSON。
2. 根据 JSON 中的 `report_type` 自动识别模板。
3. 支持三种报表模板：
   - `monthly_financial_close`
   - `weekly_business_review`
   - `weekly_ads_optimization`
4. 生成邮件标题、HTML 正文、纯文本正文。
5. 生成 delivery manifest，记录来源报表、附件、收件人角色、状态、warnings。
6. 自动从 JSON 的 `output_files.xlsx` 找到 XLSX 附件。
7. 允许通过 CLI 显式覆盖 XLSX 路径。
8. 默认复制 XLSX 到 delivery pack 的 `attachments/` 目录，方便打包和后续发送。
9. 对 `status`、warnings、reconciliation checks 做发送前 guard。
10. dry-run 模式下只生成本地文件，不访问 SMTP。

### 3.2 v1 不包含

1. 不重新生成三类报表。
2. 不重新计算财务、销售或广告指标。
3. 不从 XLSX 解析正文。
4. 不生成 PDF。
5. v1 草稿包生成不自动发送邮件；真实发送由 v1.1 的独立 `send_report_email.py` 负责。
6. 不读取 Gmail / Outlook API。
7. 不做邮件打开率、点击率追踪。
8. 不新增数据库 delivery history 表。
9. 不把收件人真实邮箱写入 git。
10. 不自动把广告 action items 写回 Amazon Ads。

### 3.3 v1.1 包含（已实现）

1. SMTP 真实发送：`send_report_email.py --delivery-pack ... --execute`。
2. 使用 Python 标准库 `smtplib` + `email.message.EmailMessage` + `ssl`，不引入第三方邮件依赖。
3. 从 delivery pack 读取 `email_subject.txt`、`email_body.html`、`email_body.txt`、`delivery_manifest.json` 和 `attachments/`。
4. 从本地 routing config 按 `report_type + audience` 解析收件人；支持 CLI `--to/--cc/--bcc` 临时覆盖。
5. 发送前 dry-run 校验 SMTP 配置、收件人、附件、send guard 和重复发送状态。
6. 真实发送后输出 `send_result.json`，记录发送状态、收件人数、附件数量、SMTP host、message id、错误信息等。
7. 默认阻止重复发送；如同一个 delivery pack 已经 `sent`，除非显式 `--force-resend`。

### 3.4 后续不在 v1.1 内

1. 不接 Gmail / Outlook Graph API；v1.1 只做通用 SMTP。
2. 不做批量 newsletter、打开率、点击率追踪。
3. 不自动合并多份报表到同一封邮件；先一份 delivery pack 对应一封邮件。
4. 不生成 PDF；如果后续需要，PDF 由 report JSON 另行生成后作为附件加入 delivery pack。
5. 不新增数据库 delivery history 表；先用 runtime `send_result.json` 存档。

---

## 4. 输入与输出

### 4.1 输入

最小输入：

```powershell
python scripts/generate_report_delivery_pack.py --report-json runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-05-11_2026-05-17/weekly_business_review_{period_key}.json --dry-run
```

可选输入：

```text
--template auto|monthly_financial_close|weekly_business_review|weekly_ads_optimization
--audience operations|shareholders|accountant|ads_operator|internal
--xlsx-path <path>
--output-dir <path>
--include-json-attachment
--allow-partial
--allow-needs-review
--copy-attachments / --no-copy-attachments
```

默认：

```text
template = auto，按 report_json.report_type 自动识别
audience = internal
copy_attachments = true
include_json_attachment = false
allow_partial = true for operations/ads_operator/internal, false for shareholders/accountant
allow_needs_review = false
```

### 4.2 输出目录

默认输出到：

```text
runtime/report_delivery/{report_type}/{scope_id}/{period_key}/
```

其中：

```text
report_type = monthly_financial_close | weekly_business_review | weekly_ads_optimization
scope_id = marketplace_id 或 profile_id；若两者都有，使用 marketplace_id_profile_id
period_key = YYYY-MM 或 YYYY-MM-DD_YYYY-MM-DD
```

示例：

```text
runtime/report_delivery/weekly_ads_optimization/ATVPDKIKX0DER_3917953989967300/2026-05-11_2026-05-17/
```

### 4.3 输出文件

v1 默认输出：

```text
email_subject.txt
email_body.html
email_body.txt
delivery_manifest.json
attachments/
  weekly_ads_optimization_{period_key}.xlsx
```

如果使用 `--include-json-attachment`，则额外复制：

```text
attachments/
  weekly_ads_optimization_{period_key}.json
```

但默认不建议把 JSON 发给股东或会计，因为 JSON 是机器接口文件，不适合作为业务附件。

---

## 5. Report JSON 与 Delivery 的关系

三类报表已经统一输出：

```text
*.json = 结构化 source of truth
*.xlsx = 人工复核和附件
```

Delivery 功能遵循：

```text
邮件标题 / 正文 / 摘要指标 = 从 JSON 生成
邮件附件 = XLSX 为主
发送保护规则 = 从 JSON status / warnings / reconciliation_checks 判断
```

禁止行为：

```text
不要从 XLSX 反解析邮件正文。
不要把邮件正文写死为静态文本，不读取 JSON 指标。
不要把 Ads API spend 覆盖 Monthly Financial Close 的 Settlement financial result。
不要把 Settlement advertising fee 覆盖 WAOR 的 Ads API optimization spend。
```

---

## 6. 模板适配器设计

### 6.1 通用接口

建议实现一个通用服务：

```text
ReportDeliveryPackService
```

内部按 `report_type` 选择 adapter：

```text
MonthlyFinancialCloseEmailTemplate
WeeklyBusinessReviewEmailTemplate
WeeklyAdsOptimizationEmailTemplate
```

每个 adapter 输出统一结构：

```text
EmailDraft
  subject: str
  body_html: str
  body_text: str
  attachments: list[AttachmentSpec]
  warnings: list[DeliveryWarning]
  send_guard: SendGuardResult
```

### 6.2 自动识别

从 JSON 根字段读取：

```json
{
  "report_type": "weekly_ads_optimization",
  "version": "v1.0",
  "status": "ok",
  "period": {...},
  "output_files": {...}
}
```

如果 `--template auto` 且 `report_type` 不支持，应失败并提示：

```text
Unsupported report_type. Supported: monthly_financial_close, weekly_business_review, weekly_ads_optimization.
```

---

## 7. 三类邮件模板内容

### 7.1 Monthly Financial Close Email

对象：股东、会计、运营负责人。

标题建议：

```text
[Monthly Close] Amazon US 2026-03 | Profit USD 537.87 | Status OK
```

正文重点：

```text
1. 月份、marketplace、status。
2. Settlement net amount。
3. Product sales amount。
4. Internal COGS。
5. Estimated operating profit。
6. Profit margin。
7. 最大费用项：advertising cost、FBA fee、refund、promotion cost 等。
8. SKU 成本覆盖状态。
9. warnings / needs_review 原因。
10. 附件说明：XLSX 多 sheet 包含 Summary、费用结构、SKU Profit、Reconciliation Checks。
```

发送 guard：

```text
status = ok：允许发送。
status = needs_review：默认不允许发给 shareholders/accountant；允许发给 internal/operations 并明确标红。
status = no_data：不允许发送，除非 --allow-empty。
```

### 7.2 Weekly Business Review Email

对象：CEO、运营负责人。

标题建议：

```text
[Weekly Business Review] Amazon US 2026-05-11..2026-05-17 | Sales USD 602.38 | Status OK
```

正文重点：

```text
1. 周期、marketplace、profile、status。
2. Sales & Traffic 销售额、units、sessions、unit session rate。
3. Ads spend、ACOS、TACOS。
4. Estimated COGS、contribution after ads。
5. SKU performance highlights。
6. Inventory risk / alerts。
7. 本周 action items。
8. 数据覆盖 warnings。
```

发送 guard：

```text
status = ok：允许发送。
status = partial：允许发给 operations/internal，但正文顶部提示 partial；不建议发给 shareholders。
status = needs_review：默认阻止，除非 --allow-needs-review。
```

### 7.3 Weekly Ads Optimization Email

对象：广告操作者、运营负责人。

标题建议：

```text
[Ads Optimization] Amazon US 2026-05-11..2026-05-17 | ACOS 38.05% | Actions 16
```

正文重点：

```text
1. 周期、marketplace、profile、status。
2. Ads spend、ads sales 7d、purchases、clicks。
3. ACOS、ROAS、TACOS。
4. Search term actions 数量。
5. Top negative candidates。
6. Top harvest exact candidates。
7. Campaign / targeting 调整方向。
8. 人工复核提醒：不自动修改 Amazon Ads。
```

发送 guard：

```text
status = ok：允许发送给 ads_operator/operations。
status = partial：允许发送，但正文提示 Ads 数据覆盖 partial。
status = no_data：不允许发送。
```

---

## 8. Audience 与收件人路由规则

v1 draft pack 已经有 `audience` 概念；v1.1 SMTP 发送需要把它扩展成“报表类型 + audience”的收件人路由。这样同一个发送脚本可以服务三类报表，但每类报表发给不同的人。

### 8.1 Audience 定义

| audience | 用途 | 默认附件 | 默认是否允许 partial | 默认是否允许 needs_review |
|---|---|---|---|---|
| `internal` | 自己复核 / 测试发送 | XLSX，可选 JSON | 是 | 可通过 `--allow-needs-review` |
| `operations` | 运营负责人/CEO | XLSX | 是 | 否 |
| `ads_operator` | 广告操作者 | XLSX | 是 | 否 |
| `shareholders` | 股东 | XLSX | 否 | 否 |
| `accountant` | 会计 | XLSX | 否 | 否 |

### 8.2 收件人配置文件

真实收件人不写入 Python 代码，不提交 git。推荐使用本地 runtime 文件：

```text
runtime/config/report_delivery_recipients.json
```

`runtime/` 已在 `.gitignore` 中，因此该文件不会被提交。

推荐配置结构：

```json
{
  "version": "v1.0",
  "defaults": {
    "reply_to": "reports@example.com"
  },
  "routes": {
    "monthly_financial_close": {
      "shareholders": {
        "to": ["shareholder1@example.com", "shareholder2@example.com"],
        "cc": ["operator@example.com"],
        "bcc": []
      },
      "accountant": {
        "to": ["accountant@example.com"],
        "cc": ["operator@example.com"],
        "bcc": []
      },
      "internal": {
        "to": ["operator@example.com"],
        "cc": [],
        "bcc": []
      }
    },
    "weekly_business_review": {
      "operations": {
        "to": ["operator@example.com"],
        "cc": [],
        "bcc": []
      },
      "internal": {
        "to": ["operator@example.com"],
        "cc": [],
        "bcc": []
      }
    },
    "weekly_ads_optimization": {
      "ads_operator": {
        "to": ["ads-operator@example.com"],
        "cc": ["operator@example.com"],
        "bcc": []
      },
      "operations": {
        "to": ["operator@example.com"],
        "cc": [],
        "bcc": []
      },
      "internal": {
        "to": ["operator@example.com"],
        "cc": [],
        "bcc": []
      }
    }
  }
}
```

### 8.3 路由解析顺序

`send_report_email.py` 解析收件人的顺序：

```text
1. 如果 CLI 显式传入 --to / --cc / --bcc，则优先使用 CLI 收件人。
2. 否则读取 --recipient-config 指定文件。
3. 如果未传 --recipient-config，则默认读取 runtime/config/report_delivery_recipients.json。
4. 在 config 中使用 report_type + audience 精确匹配。
5. 若没有匹配到收件人，发送 blocked，不允许默认乱发。
```

### 8.4 为什么不只按 audience 配置

只按 `audience=operations` 不够安全，因为不同报表的接收范围不同。例如：

```text
monthly_financial_close + shareholders -> 股东
monthly_financial_close + accountant -> 会计
weekly_business_review + operations -> 运营/CEO
weekly_ads_optimization + ads_operator -> 广告操作者
```

因此 v1.1 固定采用：

```text
report_type + audience -> to/cc/bcc
```

这样既精简，又能避免把广告动作邮件误发给股东，或把月结财务邮件误发给广告操作者。


### 8.5 当前默认收件人配置

当前小团队阶段，所有三类报表的默认路由先统一发送给：

```text
feng@cuidena.cn
yufei@cuidena.cn
qian@cuidena.cn
```

本次实现会提供一个本地 runtime 配置文件：

```text
runtime/config/report_delivery_recipients.json
```

该文件位于 `.gitignore` 覆盖的 `runtime/` 下，用于本地执行和后续服务器部署配置，不作为正式源代码提交。后续如果需要不同报表发给不同人，只需要改这个 JSON；如果需要临时测试，也可以用 `send_report_email.py --to test@example.com` 覆盖。

当前不建议新增数据库表存收件人，原因：

1. 收件人数量很少，配置变更频率低；
2. 真实发送仍是手动/半自动，不需要后台管理界面；
3. 避免新增 migration、权限管理和数据脱敏成本；
4. SMTP 密码仍必须走环境变量，不适合进数据库；
5. 后续若需要多人后台管理、发送审计和 UI 配置，再升级为 `report_delivery_recipient_route` 表。

---

## 9. Delivery manifest 结构

`delivery_manifest.json` 建议结构：

```json
{
  "delivery_type": "report_email_pack",
  "version": "v1.0",
  "generated_at": "2026-05-23T00:00:00Z",
  "dry_run": true,
  "report": {
    "report_type": "weekly_ads_optimization",
    "report_version": "v1.0",
    "status": "ok",
    "marketplace_id": "ATVPDKIKX0DER",
    "profile_id": "3917953989967300",
    "period_key": "2026-05-11_2026-05-17",
    "source_json_path": "runtime/analysis_reports/.../weekly_ads_optimization_{period_key}.json",
    "source_xlsx_path": "runtime/analysis_reports/.../weekly_ads_optimization_{period_key}.xlsx"
  },
  "email": {
    "template": "weekly_ads_optimization",
    "audience": "ads_operator",
    "subject_path": "email_subject.txt",
    "body_html_path": "email_body.html",
    "body_text_path": "email_body.txt"
  },
  "attachments": [
    {
      "kind": "xlsx",
      "source_path": "runtime/analysis_reports/.../weekly_ads_optimization_{period_key}.xlsx",
      "pack_path": "attachments/weekly_ads_optimization_{period_key}.xlsx",
      "required": true
    }
  ],
  "send_guard": {
    "send_allowed": true,
    "severity": "ok",
    "messages": []
  },
  "warnings": []
}
```

---

## 10. SMTP 真实发送设计（v1.1）

### 10.1 技术选择

v1.1 使用 Python 标准库实现，不新增第三方依赖：

```text
smtplib                     # 连接 SMTP server 并发送
email.message.EmailMessage   # 组装 MIME 邮件、HTML/text alternative、附件
ssl                          # STARTTLS / SSL context
mimetypes                    # 自动识别附件 MIME type
json / pathlib               # 读取 manifest、收件人配置和本地文件
```

选择 SMTP 而不是 Gmail/Outlook API 的原因：

```text
1. 小团队最省事，任何企业邮箱/个人邮箱/SMTP relay 都能接。
2. 不需要 OAuth app 注册、Graph API 权限、token refresh 等额外复杂度。
3. 当前发送量很低，SMTP 足够稳定。
4. 未来如果需要企业级投递，再抽象 provider 接口切到 SendGrid / SES / Microsoft Graph。
```

### 10.2 发送脚本

新增脚本建议：

```text
scripts/send_report_email.py
```

只负责发送已生成的 delivery pack，不负责重新生成报表或重新生成邮件正文。

Dry-run 校验：

```powershell
python scripts/send_report_email.py --delivery-pack runtime/report_delivery/weekly_ads_optimization/ATVPDKIKX0DER_3917953989967300/2026-05-11_2026-05-17 --audience ads_operator --dry-run
```

真实发送：

```powershell
python scripts/send_report_email.py --delivery-pack runtime/report_delivery/weekly_ads_optimization/ATVPDKIKX0DER_3917953989967300/2026-05-11_2026-05-17 --audience ads_operator --execute
```

### 10.3 SMTP 环境变量

SMTP 配置走 `.env` / 环境变量，不进入 git。

```text
REPORT_EMAIL_SMTP_HOST=smtp.example.com
REPORT_EMAIL_SMTP_PORT=587
REPORT_EMAIL_SMTP_SECURITY=starttls   # starttls | ssl | none
REPORT_EMAIL_SMTP_USERNAME=reports@example.com
REPORT_EMAIL_SMTP_PASSWORD=<app-password-or-smtp-password>
REPORT_EMAIL_FROM=reports@example.com
REPORT_EMAIL_FROM_NAME=SellerDataPipeline Reports
REPORT_EMAIL_REPLY_TO=operator@example.com
REPORT_EMAIL_SMTP_TIMEOUT_SECONDS=30
REPORT_EMAIL_SMTP_MAX_RETRIES=2
```

说明：

```text
starttls：通常对应 587 端口，先明文连接再升级 TLS，推荐默认。
ssl：通常对应 465 端口，连接时直接使用 SSL。
none：仅用于本地调试 SMTP server，不建议生产使用。
```

如果 `REPORT_EMAIL_FROM_NAME` 未配置，发件人显示名使用 `REPORT_EMAIL_FROM`。

### 10.4 收件人配置

默认读取：

```text
runtime/config/report_delivery_recipients.json
```

也可通过 CLI 指定：

```powershell
python scripts/send_report_email.py --delivery-pack runtime/report_delivery/... --audience shareholders --recipients-config runtime/config/report_delivery_recipients.json --dry-run
```

临时测试可以用 CLI 覆盖收件人：

```powershell
python scripts/send_report_email.py --delivery-pack runtime/report_delivery/... --to my-test-email@example.com --dry-run
```

CLI 覆盖适合首次测试；长期使用应依赖 `report_type + audience` 路由配置。

### 10.5 发送前校验

`send_report_email.py --execute` 必须在发送前检查：

```text
1. delivery_pack 目录存在。
2. delivery_manifest.json 存在且 JSON 可解析。
3. email_subject.txt 存在且非空。
4. email_body.html 或 email_body.txt 至少一个非空。
5. send_guard.send_allowed = true，除非显式 --override-send-guard。
6. report status 与 audience 规则兼容。
7. 至少有一个 to 收件人。
8. SMTP host / port / username / password / from 配置完整。
9. 所有 required attachments 存在。
10. 附件总大小未超过 `--max-attachment-mb`，默认 20MB。
11. 如果已有 send_result.json 且 status=sent，默认 blocked，除非 --force-resend。
```

### 10.6 邮件内容组装

邮件结构：

```text
Subject: email_subject.txt
From: REPORT_EMAIL_FROM_NAME <REPORT_EMAIL_FROM>
To/Cc/Bcc: resolved recipients
Reply-To: REPORT_EMAIL_REPLY_TO 或 recipients config defaults.reply_to
Body: multipart/alternative
  - text/plain: email_body.txt
  - text/html: email_body.html
Attachments:
  - attachments/*.xlsx
  - optional JSON only if delivery pack included it
```

BCC 不写入邮件正文，只作为 SMTP envelope recipient。

### 10.7 发送结果文件

真实发送后写入：

```text
send_result.json
```

建议结构：

```json
{
  "delivery_type": "report_email_send",
  "version": "v1.0",
  "sent_at": "2026-05-23T00:00:00Z",
  "status": "sent",
  "dry_run": false,
  "report_type": "weekly_ads_optimization",
  "audience": "ads_operator",
  "to_count": 1,
  "cc_count": 1,
  "bcc_count": 0,
  "attachment_count": 1,
  "smtp_host": "smtp.example.com",
  "smtp_port": 587,
  "smtp_security": "starttls",
  "message_id": "<generated-message-id>",
  "warnings": []
}
```

如果失败：

```json
{
  "status": "failed",
  "error_type": "smtp_auth_failed",
  "error_message": "Authentication failed",
  "sent_at": null
}
```

不在 `send_result.json` 中写入 SMTP password。

### 10.8 重试策略

建议：

```text
SMTP 连接超时 / 临时网络错误：最多重试 REPORT_EMAIL_SMTP_MAX_RETRIES 次。
SMTP 认证失败：fail fast，不重试太多。
收件人配置缺失 / 附件缺失 / send guard blocked：不重试，直接 blocked。
```

### 10.9 安全与误发防护

1. `--dry-run` 是默认安全路径；真实发送必须显式 `--execute`。
2. `needs_review` 默认不发；`partial` 不发给 shareholders/accountant。
3. 真实发送前打印 resolved recipients、subject、attachments、send_guard。
4. 已发送过的 pack 默认不重复发送。
5. 密码只从环境变量读取，不打印、不写入 JSON。
6. 收件人配置放在 `runtime/config/`，不提交 git。
---

## 11. 推荐命令流

### 11.1 单份报表生成 delivery pack

Monthly：

```powershell
python scripts/generate_report_delivery_pack.py --report-json runtime/analysis_reports/monthly_financial_close/ATVPDKIKX0DER/2026-04/monthly_financial_close_{YYYY-MM}.json --audience shareholders --dry-run
```

WBR：

```powershell
python scripts/generate_report_delivery_pack.py --report-json runtime/analysis_reports/weekly_business_review/ATVPDKIKX0DER/2026-05-11_2026-05-17/weekly_business_review_{period_key}.json --audience operations --dry-run
```

WAOR：

```powershell
python scripts/generate_report_delivery_pack.py --report-json runtime/analysis_reports/weekly_ads_optimization/3917953989967300/2026-05-11_2026-05-17/weekly_ads_optimization_{period_key}.json --audience ads_operator --dry-run
```

### 11.2 发送前人工检查

人工打开：

```text
email_subject.txt
email_body.html
attachments/*.xlsx
```

确认：

```text
1. 指标是否合理。
2. warnings 是否可接受。
3. 附件是否正确。
4. audience 是否正确。
5. 收件人是否正确。
```

### 11.3 后续真实发送

先 dry-run 检查 SMTP、收件人、附件和 guard：

```powershell
python scripts/send_report_email.py --delivery-pack runtime/report_delivery/... --audience ads_operator --dry-run
```

确认无误后 execute：

```powershell
python scripts/send_report_email.py --delivery-pack runtime/report_delivery/... --audience ads_operator --execute
```

首次测试建议用 CLI 临时覆盖收件人，把邮件只发给自己：

```powershell
python scripts/send_report_email.py --delivery-pack runtime/report_delivery/... --to my-test-email@example.com --execute
```

---

## 12. 错误处理与状态

### 12.1 生成 pack 错误

| 错误 | 行为 |
|---|---|
| report_json 不存在 | fail fast |
| JSON 格式错误 | fail fast |
| unsupported report_type | fail fast |
| output_files.xlsx 缺失 | fail fast；除非显式 `--xlsx-path` |
| xlsx 文件不存在 | fail fast |
| report status = no_data | 默认 fail guard |
| report status = needs_review | 默认 fail guard；可生成 internal pack，但不允许 shareholder/accountant send |
| partial report + shareholder/accountant | 默认 fail guard |

### 12.2 发送错误

| 错误 | 行为 |
|---|---|
| SMTP 配置缺失 | 不发送，返回 failed |
| 收件人为空 | 不发送，返回 failed |
| report_type + audience 找不到 route | 不发送，返回 blocked |
| required attachment 缺失 | 不发送，返回 failed |
| 附件总大小超过限制 | 不发送，返回 blocked |
| send_guard 不允许 | 不发送，返回 blocked |
| 已有 `send_result.json` 且 status=sent | 默认 blocked，除非 `--force-resend` |
| SMTP 连接失败 | retry 1-2 次后 failed |
| SMTP 认证失败 | fail fast，不重试太多 |

---

## 13. 测试计划

### 13.1 Unit tests

1. 自动识别三类 `report_type`。
2. Monthly 模板能从 JSON 生成 subject/body。
3. WBR 模板能从 JSON 生成 subject/body。
4. WAOR 模板能从 JSON 生成 subject/body。
5. 缺 XLSX 路径时 fail。
6. `status=needs_review` 对 shareholders 触发 guard。
7. `status=partial` 对 operations 允许、对 shareholders 不允许。
8. `delivery_manifest.json` 路径和附件列表正确。
9. HTML body 和 text body 都非空。
10. JSON 附件默认不包含，`--include-json-attachment` 后包含。
11. SMTP config validation 缺字段时 blocked/failed。
12. `report_type + audience` 能正确解析收件人 route。
13. CLI `--to/--cc/--bcc` 能覆盖 config route。
14. required attachment 缺失时不发送。
15. 已有 successful `send_result.json` 时默认阻止重复发送。
16. SMTP sender 使用 fake SMTP client/mock 时能组装 subject、HTML/text body 和 XLSX attachment。

### 13.2 Manual verification

使用已有真实样本：

```text
Monthly Financial Close：2026-03 / 2026-04
Weekly Business Review：2026-05-11..2026-05-17
Weekly Ads Optimization：2026-05-11..2026-05-17
```

验证：

```text
1. 三类 pack 均可生成。
2. 邮件正文指标与 JSON/XLSX 一致。
3. XLSX 附件可打开。
4. status/warnings 展示清楚。
5. 不产生外部发送动作。
```

---

## 14. 实现建议

新增文件：

```text
scripts/generate_report_delivery_pack.py
src/seller_data_pipeline/services/report_delivery_service.py
src/seller_data_pipeline/services/report_delivery_templates.py
tests/unit/services/test_report_delivery_service.py
tests/unit/services/test_report_delivery_templates.py
```

后续 SMTP 发送新增：

```text
scripts/send_report_email.py
src/seller_data_pipeline/services/report_email_sender.py
tests/unit/services/test_report_email_sender.py
```

不新增：

```text
sql/migrations/*
report_delivery database tables
```

---

## 15. 验收标准

v1 验收：

```text
1. 三类报表 JSON 均能生成 delivery pack。
2. 每个 pack 至少包含 subject、HTML body、text body、manifest、XLSX attachment。
3. 邮件正文核心指标来自 JSON，和报表输出一致。
4. needs_review / partial / no_data guard 生效。
5. 默认不发送任何邮件。
6. 通过 ruff、unit tests、compileall。
```

v1 实现文件：

```text
scripts/generate_report_delivery_pack.py
src/seller_data_pipeline/services/report_delivery_service.py
src/seller_data_pipeline/services/report_delivery_templates.py
tests/unit/services/test_report_delivery_service.py
tests/unit/services/test_report_delivery_templates.py
```

v1 本轮验证：

```text
PYTHONPATH=src pytest tests/unit -q -> 271 passed
python -m compileall -q scripts src tests -> passed
ruff 未在当前 sandbox 安装，需在本地/GitHub Action 执行。
```

已用三类真实样本验证草稿包生成：

```text
Monthly Financial Close：2026-04 / shareholders / send_allowed=true
Weekly Business Review：2026-05-11..2026-05-17 / operations / send_allowed=true
Weekly Ads Optimization：2026-05-11..2026-05-17 / ads_operator / send_allowed=true
```

v1.1 验收：

```text
1. send_report_email.py dry-run 可读取 pack 并展示收件人/附件/guard 状态。
2. --execute 可通过 SMTP 发送测试邮件。
3. 无收件人、SMTP 配置缺失、附件缺失、guard blocked 均不会发送。
4. 发送后生成 send_result.json。
```

---

## 16. 当前结论

Report Delivery 应作为统一功能开发，而不是为三份报表分别开发三套邮件脚本。

推荐开发顺序：

```text
1. generate_report_delivery_pack.py 已实现：生成草稿包，不发送。
2. 三类真实报表 JSON 已验证模板可生成。
3. 下一步人工检查 email_body.html 与附件。
4. `send_report_email.py` 已实现：默认 dry-run，--execute 才真实发送。
5. 最后才接入 weekly_full / Azure Jobs。
```

---

## 17. v1.3 Bilingual delivery requirement

After the first successful SMTP test email, report delivery is upgraded to bilingual output.

Scope:

```text
1. Email subject keeps both Chinese and English report names.
2. Email HTML/text body is Chinese-first, with English reference text preserved.
3. Key metric labels are rendered as Chinese / English.
4. Action recommendations are rendered with Chinese explanations plus English source text.
5. XLSX workbooks add `00_Readme_说明` and bilingual fixed headers/labels.
```

Important boundary:

```text
Amazon-native source data is not translated:
- campaign names
- ad group names
- search terms
- keywords
- SKU / ASIN
- raw IDs
```

Reason:

```text
These values must stay identical to Amazon Ads Console / Seller Central so operators can copy,
search and reconcile them without accidental mistranslation.
```

Implementation note:

```text
JSON remains the machine-readable source of truth and keeps stable English field names.
Bilingual rendering is applied at the email/XLSX presentation layer.
```
