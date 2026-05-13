# SellerDataPipeline 当前进展与下一步计划

> 文档用途：本文件用于记录当前实际完成进展、阶段结论和下一步开发计划。后续应与《Amazon Profit Report Serverless Design Plan v1.1》配合使用。设计文档负责定义长期架构和目标，本文件负责记录当前执行状态和近期落地顺序。

---

## 1. 项目目标简述

SellerDataPipeline 是一个用于亚马逊卖家运营与财务数据自动化的轻量级数据管道项目。

项目长期目标是：

1. 自动从 Amazon SP-API 和 Amazon Ads API 获取销售、财务、库存、广告、Listing、品牌分析和用户反馈相关数据。
2. 将原始数据和标准化数据存入 Azure SQL Database。
3. 使用 Azure Container Apps Job 定时运行数据同步、报告收集和周期报表生成任务。
4. 自动生成：
   - 每周运营快报
   - 上上完整周稳定盈亏报
   - 月度财务包
   - 季度会计/报税准备数据包
5. 生成 Excel 报表并通过邮件发送，同时保留运行日志和报表版本记录。

当前项目暂不做 Django 后台，也暂不做实时网页看板。第一阶段重点是打通 SP-API 数据链路和异步报告流程。

---

## 2. 当前已完成进展

### 2.1 GitHub 项目初始化

已完成项目仓库创建，并已生成初始项目骨架。

当前项目基础结构包括：

```text
README.md
Dockerfile
requirements.txt
pyproject.toml
.env.example
sql/migrations/
sql/seeds/
src/seller_data_pipeline/
scripts/
tests/
.github/workflows/ci.yml
```

已建立的开发规范包括：

1. `src/seller_data_pipeline/` 存放核心业务逻辑。
2. `scripts/` 存放本地和云端 Job 的薄入口脚本。
3. `tests/` 存放单元测试和后续集成测试。
4. `sql/migrations/` 存放数据库建表和结构变更脚本。
5. `.env.example` 只保留环境变量示例，不存放真实密钥。
6. `.env` 仅用于本地开发，必须保持不提交 GitHub。

---

### 2.2 代码质量与 CI 修复

之前从 `dev` 合并到 `main` 时，GitHub Actions 中 `ruff check src tests` 报错，主要问题包括：

1. import 顺序不符合 Ruff/isort 规则。
2. 少数行超过 `line-length = 100`。
3. `typing.Iterator` 需要改为 `collections.abc.Iterator`。

已完成修复。

当前状态：

```text
ruff check src tests scripts：通过
pytest -q tests/unit：通过
```

建议后续本地提交前固定运行：

```bash
ruff check src tests scripts --fix
ruff format src tests scripts
PYTHONPATH=src pytest -q tests/unit
```

---

### 2.3 Azure 基础资源检查

已创建 Azure SQL Database 免费数据库。

当前确认状态：

1. SQL 数据库为 Free tier。
2. Pricing tier 为 Free - General Purpose - Serverless。
3. Overage billing 为 Disabled。
4. 数据库曾显示为 Paused 状态。
5. Azure Cost analysis 当前显示资源组费用为 £0.00。
6. 资源组 `rg-amazon-ops` 当前未产生实际费用。

已确认：当前看到的 Azure available credits 不是因为 SQL 免费数据库产生实际花费。后续每创建一个 Azure 资源，都应回到 Cost analysis 按 Resource 查看费用。

建议继续保持：

1. SQL 免费额度内使用。
2. 不开启 overage billing。
3. 不创建 VM、NAT Gateway、Public IP、Application Gateway 等容易产生固定费用的资源。
4. 后续创建 Container Apps、Container Registry、Key Vault、Storage、Log Analytics 后立即检查 Cost analysis。

---

### 2.4 SP-API Developer Profile 已创建并获批

已完成 Amazon Solution Provider Portal 中的 SP-API Developer Profile 申请。

申请类型为内部自用方向，用于创建使用 SP-API 的应用程序。

申请中已按内部数据管道用途说明：

1. 公司通过 Amazon Seller Central 销售自有品牌消费品。
2. 主要使用 FBA 履约。
3. SP-API 用于内部运营、财务、库存、Listing、品牌分析和用户反馈分析。
4. 数据用于周报、月报、季度会计数据包和产品改进决策。
5. 应用不会上架 Amazon Appstore，也不会提供给外部卖家。

Amazon 已返回：

```text
SP-API Developer Profile Created
SP-API 访问权限申请已批准
可以注册销售伙伴 API 应用程序
```

---

### 2.5 SP-API Production Private App 已创建

已创建 Production 类型 SP-API 应用。

应用信息：

```text
Application name: SellerDataPipeline
API type: SP API
App Type: Production
Business entity supported: Seller
```

已选择 6 个 Role：

```text
Finance and Accounting
Selling Partner Insights
Inventory and Order Tracking
Brand Analytics
Amazon Fulfillment
Product Listing
```

未选择 RDT / PII 委派访问。

当前策略：

1. 暂不主动申请买家 PII 相关权限。
2. 暂不使用 Restricted 税务发票、税款汇缴、买家通讯等高敏感权限。
3. 季度报税目标定位为“会计数据包”，不是系统直接执行税务申报。

---

### 2.6 SP-API 自授权已完成

已完成 Private App 自授权，并已取得以下三项核心凭证：

```text
AMAZON_LWA_CLIENT_ID
AMAZON_LWA_CLIENT_SECRET
AMAZON_SP_API_REFRESH_TOKEN
```

这些值已由用户本地保存。

安全要求：

1. 不得提交到 GitHub。
2. 本地开发时放入 `.env`。
3. `.env` 必须在 `.gitignore` 中。
4. 云端正式部署时应放入 Azure Key Vault。
5. 后续不在日志中打印完整 token、secret、refresh token。

---

### 2.7 SP-API 本地连通性测试已完成

已新增 SP-API 本地连接测试脚本：

```text
scripts/test_sp_api_connection.py
```

已实现：

1. 从 `.env` 读取 Amazon SP-API 配置。
2. 使用 LWA refresh token 换取 access token。
3. 调用 SP-API `GET /sellers/v1/marketplaceParticipations`。
4. 打印当前账号参与的 marketplace。

本地测试命令：

```bash
$env:PYTHONPATH="src"
python scripts/test_sp_api_connection.py
```

测试结果成功，返回 7 个 marketplace：

```text
A1AM78C64UM0Y8 | Amazon.com.mx | MX | MXN
A1MQXOICRS2Z7M | Non-Amazon CA | CA | CAD
A2EUQ1WTGCTBG2 | Amazon.ca | CA | CAD
A2Q3Y263D00KWC | Amazon.com.br | BR | BRL
A2ZV50J4W1RKNI | Non-Amazon US | US | USD
A3H6HPSLHAK3XG | Non-Amazon MX | MX | MXN
ATVPDKIKX0DER | Amazon.com | US | USD
```

当前第一版只处理美国站：

```text
Marketplace: Amazon.com
Country: US
Currency: USD
Marketplace ID: ATVPDKIKX0DER
Region: NA
Endpoint: https://sellingpartnerapi-na.amazon.com
```

阶段结论：

```text
SP-API Developer Profile：完成
Production Private App：完成
Self Authorization：完成
LWA token exchange：完成
SP-API endpoint connectivity：完成
Marketplace participation test：完成
```

---

## 3. 当前阶段结论

当前项目已经完成从“账号权限准备”到“SP-API 本地连通性验证”的第一阶段。

这说明：

1. Amazon 账号和应用权限方向正确。
2. SP-API 生产环境授权有效。
3. 本地 Python 项目可以成功访问 Amazon SP-API。
4. 后续可以正式进入 Reports API 异步报告流程开发。

当前尚未完成：

1. Reports API `createReport` 流程。
2. 报告请求状态表 `amazon_report_request`。
3. 报告轮询、下载、解压、解析。
4. Azure SQL 写入和 upsert。
5. 周报/月报/季报 Excel 生成。
6. Amazon Ads API 接入。
7. Azure Container Apps Job 云端部署。

---

## 4. 下一步总体开发方向

下一阶段的核心目标是打通 **Reports API 异步报告任务队列流程**。

设计原则：

```text
不要让一个 Job 长时间等待报告生成。
应拆成：提交报告请求 → 定时检查报告状态 → 下载解析入库 → 生成周期报表。
```

目标流程：

```text
submit_report_requests
    ↓
调用 createReport
    ↓
写入 amazon_report_request 表
    ↓
collect_ready_reports
    ↓
调用 getReport 查询状态
    ↓
DONE 后调用 getReportDocument
    ↓
下载报告文件
    ↓
解压/解析
    ↓
upsert 入 Azure SQL
    ↓
generate_periodic_reports
    ↓
生成周报/月报/季报
```

---

## 5. 下一步详细计划

### 5.1 第一步：补齐数据库基础表设计

优先新增 SQL migration。

建议新增文件：

```text
sql/migrations/003_create_report_request_tables.sql
```

第一批重点表：

```text
amazon_report_request
amazon_sync_run_log
```

`amazon_report_request` 用于记录每一个 Amazon report 请求的生命周期。

核心字段建议：

```text
id
marketplace
report_type
data_start_time
data_end_time
report_id
report_document_id
processing_status
submit_status
download_status
parse_status
requested_at
last_checked_at
completed_at
downloaded_at
parsed_at
retry_count
error_message
raw_file_path
created_at
updated_at
```

`amazon_sync_run_log` 用于记录每次 Job 执行状态。

核心字段建议：

```text
id
job_name
run_id
started_at
finished_at
status
date_start
date_end
message
error_detail
created_at
```

验收标准：

1. SQL migration 文件完成。
2. 表结构支持 report lifecycle tracking。
3. 本地可执行建表 SQL。
4. 字段名与设计文档 v1.1 保持一致或明确记录差异。

---

### 5.2 第二步：实现 Reports API 基础客户端

在现有 SP-API client 基础上新增 Reports API 方法。

建议文件：

```text
src/seller_data_pipeline/integrations/amazon/reports_api_client.py
```

或者在现有：

```text
src/seller_data_pipeline/integrations/amazon/sp_api_client.py
```

中增加独立方法。

需要实现：

```text
create_report(report_type, marketplace_ids, data_start_time, data_end_time)
get_report(report_id)
get_report_document(report_document_id)
download_report_document(download_url, compression_algorithm)
```

验收标准：

1. 能成功调用 `createReport`。
2. 能拿到 `reportId`。
3. 能调用 `getReport` 查询状态。
4. 能处理 `IN_QUEUE`、`IN_PROGRESS`、`DONE`、`FATAL`、`CANCELLED` 等状态。
5. 不在日志中打印敏感 token。

---

### 5.3 第三步：实现提交报告请求 Job

建议入口脚本：

```text
scripts/submit_report_requests.py
```

建议业务文件：

```text
src/seller_data_pipeline/jobs/submit_report_requests_job.py
src/seller_data_pipeline/services/submit_report_requests_service.py
```

职责：

1. 计算日期窗口。
2. 根据配置选择 report type。
3. 调用 `createReport`。
4. 将 `reportId` 和请求参数写入 `amazon_report_request`。
5. 写入 `amazon_sync_run_log`。

第一版建议先只测试一个 report type，不要一次上所有报告。

可选候选报告：

```text
GET_MERCHANT_LISTINGS_ALL_DATA
GET_MERCHANT_LISTINGS_DATA
GET_FLAT_FILE_OPEN_LISTINGS_DATA
```

后续再逐步接：

```text
Sales and Traffic
Finance / settlement
Inventory
Promotion / coupon
Brand Analytics
Customer Feedback
```

验收标准：

1. 本地运行 submit 脚本成功。
2. Amazon 返回 reportId。
3. 数据库中新增一条 report request 记录。
4. 状态为 SUBMITTED / IN_QUEUE。
5. 重复运行不会造成不可控重复数据，后续需要补充幂等策略。

---

### 5.4 第四步：实现报告状态检查与下载 Job

建议入口脚本：

```text
scripts/collect_ready_reports.py
```

建议业务文件：

```text
src/seller_data_pipeline/jobs/collect_ready_reports_job.py
src/seller_data_pipeline/services/collect_ready_reports_service.py
```

职责：

1. 从 `amazon_report_request` 查询未完成报告。
2. 调用 `getReport` 更新状态。
3. 如果状态为 `IN_QUEUE` 或 `IN_PROGRESS`，更新 `last_checked_at` 后退出。
4. 如果状态为 `DONE`，获取 `reportDocumentId`。
5. 调用 `getReportDocument` 获取下载 URL。
6. 下载报告文件。
7. 必要时处理 gzip 等压缩格式。
8. 保存原始文件路径。
9. 更新状态为 DOWNLOADED。
10. 后续接 parser 后更新为 PARSED。

验收标准：

1. 能识别 pending report。
2. 能正确更新状态。
3. DONE 后能成功下载文件。
4. 原始文件能保存到本地临时目录或后续 Azure Blob。
5. 异常状态能写入 error_message，不死循环。

---

### 5.5 第五步：实现第一个报告解析器

建议目录：

```text
src/seller_data_pipeline/parsers/
```

先做一个最简单的报告解析器，用于验证解析框架。

建议文件示例：

```text
src/seller_data_pipeline/parsers/listing_report_parser.py
```

解析器职责：

1. 接收原始报告文件。
2. 识别分隔符和编码。
3. 解析为标准化 Python dict/list。
4. 对字段进行基础清洗。
5. 返回可入库的数据结构。

验收标准：

1. 使用 fixture 样例文件可以稳定解析。
2. 有单元测试覆盖。
3. 遇到空文件、缺字段、格式异常时有明确错误。

---

### 5.6 第六步：接入 Azure SQL 写入

在报告下载和解析完成后，接入 Azure SQL。

优先实现：

```text
src/seller_data_pipeline/db/azure_sql.py
src/seller_data_pipeline/db/repositories/report_request_repo.py
src/seller_data_pipeline/db/repositories/sync_run_log_repo.py
```

第一阶段只需实现：

1. 连接 Azure SQL。
2. 插入 report request。
3. 更新 report request 状态。
4. 写入 sync run log。
5. 对第一个解析后的报告做简单入库。

验收标准：

1. `.env` 中配置 Azure SQL 后，本地可以连接数据库。
2. submit job 能写入 `amazon_report_request`。
3. collect job 能更新记录状态。
4. 失败时能记录日志。

---

### 5.7 第七步：再扩展财务、销售和库存数据

当一个报告完整跑通后，再扩展核心经营数据。

优先顺序建议：

```text
1. Listing / 商品信息报告
2. Inventory / 库存报告
3. Sales / 销售流量报告
4. Finance / settlement / transaction 数据
5. Promotion / coupon 数据
6. Brand Analytics / Customer Feedback insights
7. Amazon Ads API 广告数据
```

注意：广告数据属于 Amazon Ads API，不是当前 SP-API 流程的一部分，建议等 SP-API Reports 链路稳定后再接。

---

## 6. 后续里程碑建议

### Milestone 1：SP-API 基础连通性完成

状态：已完成。

完成内容：

```text
Developer Profile approved
Private Production App created
Self authorization completed
Local SP-API connection test succeeded
```

---

### Milestone 2：Reports API 异步流程跑通

目标：

```text
createReport → getReport → getReportDocument → download report
```

完成标准：

1. 成功提交一个 report request。
2. 成功查询状态。
3. DONE 后成功下载原始报告。
4. 状态记录在数据库或本地状态文件中。

---

### Milestone 3：Azure SQL 状态管理跑通

目标：

```text
amazon_report_request + amazon_sync_run_log 可用
```

完成标准：

1. submit job 写入 report request。
2. collect job 更新 report status。
3. 异常记录进入 run log。
4. 支持重复运行和失败恢复。

---

### Milestone 4：第一个报告解析并入库

目标：

```text
下载的 Amazon report 能解析为标准化数据并写入 Azure SQL
```

完成标准：

1. 有 parser。
2. 有 fixture。
3. 有单元测试。
4. 数据可 upsert。

---

### Milestone 5：核心经营数据同步

目标：

```text
销售、库存、财务基础数据可同步
```

完成标准：

1. 能按最近 45 天回刷。
2. 能避免重复插入。
3. 能支持美国站数据。
4. 能为周报计算提供基础数据。

---

### Milestone 6：周报 MVP

目标：

```text
生成最近完整周运营快报 + 上上完整周稳定盈亏报
```

完成标准：

1. 能从 Azure SQL 读取数据。
2. 能计算销售额、费用、库存和初步利润。
3. 能生成 Excel。
4. 能本地保存，后续再邮件发送。

---

### Milestone 7：Azure Container Apps Job 部署

目标：

```text
本地脚本转为云端定时 Job
```

完成标准：

1. Docker 镜像可构建。
2. 镜像推送到 Azure Container Registry。
3. Container Apps Job 可手动触发。
4. 后续配置定时触发。
5. 密钥从 Azure Key Vault 获取。

---

## 7. 当前推荐的下一次开发任务

下一次最推荐先做：

```text
Reports API 最小闭环 v0
```

范围控制如下：

1. 新增 `amazon_report_request` 和 `amazon_sync_run_log` SQL migration。
2. 新增 Reports API client 方法：`create_report`、`get_report`、`get_report_document`。
3. 新增 `scripts/submit_report_requests.py`。
4. 新增 `scripts/collect_ready_reports.py`。
5. 先选择一个简单 report type 做验证。
6. 第一版可以先把 report request 状态写到 Azure SQL；如果 Azure SQL 接入暂时未准备好，可先写本地 JSON 状态文件做临时验证，但最终应回到 Azure SQL。

建议下一次完成后可以运行：

```bash
$env:PYTHONPATH="src"
python scripts/submit_report_requests.py --report-type GET_MERCHANT_LISTINGS_ALL_DATA

$env:PYTHONPATH="src"
python scripts/collect_ready_reports.py --limit 10
```

预期结果：

```text
成功创建 reportId
成功查询报告状态
若状态 DONE，成功下载报告文件
若状态未完成，状态被正确记录，等待下一次 collect
```

---

## 8. 开发注意事项

### 8.1 不提交敏感信息

禁止提交：

```text
.env
local_credentials_notes.md
Amazon refresh token
LWA client secret
Azure SQL password
SMTP password
任何真实 token 或 secret
```

### 8.2 日志脱敏

日志中不得输出完整：

```text
access_token
refresh_token
client_secret
database password
```

如需排查，只输出前后几位并打码。

### 8.3 先小闭环，后扩展

不要一次接所有报告类型。

推荐顺序：

```text
认证测试 → 一个报告 → 状态表 → 下载 → 解析 → 入库 → 更多报告 → 周报 → 云端部署
```

### 8.4 所有周期数据需要支持回刷

未来每日同步不应只拉昨天数据。

核心原则：

```text
每天回刷最近 45 天数据
每次使用 upsert
周报重新计算最近 8 周
```

原因：

1. 广告销售归因会延迟。
2. 退款会延迟。
3. 赔偿和调整会延迟。
4. 报表生成和财务入账可能有时间差。

### 8.5 季度报税包需要版本锁定

未来季报不应无限自动覆盖。

建议状态：

```text
draft
stable
locked
amended
```

会计确认后应锁定版本，并记录生成时间、数据范围、原始 reportId 和文件路径。

---

## 9. 当前项目状态摘要

```text
项目骨架：完成
代码质量 CI：完成
Azure SQL 免费库：已创建并检查费用为 £0.00
SP-API Developer Profile：已获批
SP-API Private Production App：已创建
SP-API Roles：6 个 Role 已选
Self Authorization：已完成
LWA Client ID / Secret / Refresh Token：已取得并本地保存
SP-API 本地连接测试：成功
当前主 marketplace：Amazon.com / US / ATVPDKIKX0DER
下一阶段：Reports API 异步报告流程
```

---

## 10. 下一步一句话目标

下一步的核心目标是：

```text
在本地成功完成第一个 Amazon Reports API 异步报告闭环：
createReport → getReport → getReportDocument → download report → record status。
```

这个闭环跑通后，整个系统的后续开发都会围绕同一模式扩展。

---

## 11. 2026-05-13 数据库设计阶段更新

已新增并冻结第一版数据库唯一事实文档：

```text
requirements/database_spec.md
```

本阶段进一步明确：数据库尚未建表，因此当前 `sql/migrations/001_create_core_tables.sql` 和 `002_create_indexes.sql` 暂不应直接执行。后续数据库结构必须先更新 `requirements/database_spec.md`，再更新 SQL。

新的开发策略为：

```text
先 raw，后 normalized。
先样例，后字段。
先 spec，后 SQL。
先采集闭环，后分析报表。
控制表先稳定，业务表边取样边确认。
```

下一步不急于创建所有业务表，而是优先实现本地 Sampling Mode 和 Amazon Reports API 最小下载闭环：

1. 提交 Listing 类 report request。
2. 记录本地 request manifest。
3. 轮询 report 状态。
4. 下载 raw report 文件。
5. 保存 sha256、encoding、row_count、column_count 等 manifest 信息。
6. 提取 header 和样例行。
7. 用真实字段反向更新 `database_spec.md`。

待第一批真实字段确认后，再重写并执行数据库 SQL migration。
