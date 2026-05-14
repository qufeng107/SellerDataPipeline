# SellerDataPipeline 数据库唯一事实设计 Spec

> 文档版本：v1.4  
> 更新日期：2026-05-14  
> 当前状态：Azure SQL Database 已开通，但尚未建表；`sql/migrations/` 里的 SQL 暂视为草稿，执行前必须重新对齐本文档。  
> 适用范围：Amazon SP-API Reports / Amazon Ads Reporting / Finances API / 原始数据归档 / 字段取样 / 周报、月报、季度会计数据包。

---

## 0. 本次 v0.9 核心决策

本项目当前处于 **接口取样和数据模型探索阶段**。不要在没有真实 Amazon 样例数据前，把所有业务表和字段一次性建死。

v0.8 已完成 Settlement 财务取样：通过 `getReports` 发现 8 份 `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` 自动生成报告，并全部下载 raw file。聚合样例共 4,911 行，其中 8 行为 settlement summary，4,903 行为交易明细。真实样例确认了 Order、Refund、ServiceFee、AmazonFees、Liquidations、FBA Inventory Reimbursement、Coupon / Deal fee、Storage Fee、Subscription Fee、FBA Inbound Placement Service Fee 等费用类型。parser 需要继承 summary 行中的 settlement period / currency / total amount 到后续明细行，并生成第一版 `amount_category` / `profit_bucket` 分类字段。当前仍不执行 SQL 建表。

v0.9 新增批量取样计划：在正式建库前，先通过 `scripts/run_sampling_plan.py` 系统性提交/发现更多 Reports API 数据源，包括订单、退货、赔偿、费用预估、仓储费、库存健康、库存流水、促销/Coupon 等候选报告。默认批量计划会避开可能包含客户 PII 或客户评论的敏感报告；如业务确需取样，必须显式使用 `--include-sensitive`，并继续保证 `reports/raw/` 与 `runtime/` 不提交 GitHub。


v0.2 的核心设计决策是：

```text
先 raw，后 normalized。
先样例，后字段。
先 spec，后 SQL。
先采集闭环，后分析报表。
控制表先稳定，业务表边取样边确认。
```

因此后续开发分为两条并行线：

1. **接口取样线**：先实现 Amazon 报告提交、轮询、下载，把真实原始文件保存下来，并生成字段样例清单。
2. **数据库设计线**：每拿到一种真实 report/API 样例，就先更新本文档中的字段来源、目标表、字段状态，再决定是否生成或修改 SQL。

在数据库正式执行初始 SQL 前，允许重写：

```text
sql/migrations/001_create_core_tables.sql
sql/migrations/002_create_indexes.sql
```

一旦初始 SQL 已经在正式 Azure SQL 中执行，历史 migration 就不可再改，只能新增 `003_xxx.sql`、`004_xxx.sql`。

---


## 0.3 促销 / Coupon 报告诊断与成功取样结论 v1.3

2026-05-14 取样中，`GET_PROMOTION_PERFORMANCE_REPORT` 与
`GET_COUPON_PERFORMANCE_REPORT` 在未提供专用 `reportOptions` 时会生成 `FATAL`
diagnostic document。诊断文件确认：

```text
GET_PROMOTION_PERFORMANCE_REPORT 需要 promotionStartDateFrom / promotionStartDateTo
GET_COUPON_PERFORMANCE_REPORT    需要 couponStartDateFrom / couponStartDateTo
```

因此批量取样计划已调整为：

```text
GET_PROMOTION_PERFORMANCE_REPORT days=89
  reportOptions.promotionStartDateFrom = {data_start_time}
  reportOptions.promotionStartDateTo   = {data_end_time}

GET_COUPON_PERFORMANCE_REPORT days=89
  reportOptions.couponStartDateFrom = {data_start_time}
  reportOptions.couponStartDateTo   = {data_end_time}
```

这两个报告即使继续失败，也不阻塞第一版建库。促销、Coupon 成本第一版仍以
Settlement V2 的金额明细为主口径；Performance report 仅作为活动效果补充口径。



## 0.4 Amazon Ads API 取样阶段 v1.4

2026-05-14 起，项目进入 Amazon Ads API 取样阶段。SP-API Reports 已覆盖订单、库存、财务、销售流量、促销/Coupon 等经营数据；Ads API 用于补充广告运营口径，尤其是 campaign、targeting、search term、advertised product、purchased product 维度。

Ads API 与 SP-API Reports 分开处理：

```text
SP-API Reports:      经营事实、库存、订单、财务结算、促销/Coupon财务口径
Amazon Ads API:      广告投放结构、点击、曝光、花费、广告归因销售、搜索词表现
```

当前新增本地取样路径：

```text
runtime/sampling/ads_profiles.json
runtime/sampling/ads_report_requests/{ads_report_id}.json
runtime/sampling/ads_raw_files/{ads_report_id}.json
reports/raw/amazon_ads/{profile_id}/{report_type_id}/{date}/{ads_report_id}.json
```

当前 Ads 表仍为 `draft`，必须等待真实 Ads raw report 下载并分析后再进入 `sampling`。第一批候选表：

```text
amazon_ads_profile
amazon_ads_sp_campaign_daily
amazon_ads_sp_targeting_daily
amazon_ads_sp_search_term_daily
amazon_ads_sp_advertised_product_daily
amazon_ads_sp_purchased_product_daily
```

利润核算原则：Ads API 的 cost / sales / purchases 用于广告运营分析；最终利润核算中的广告实际扣费，仍优先以 Settlement V2 财务明细为准。

## 1. 文档定位与执行规则

本文档是 SellerDataPipeline 项目的 **数据库唯一事实来源**。

所有数据库相关变更必须遵守：

```text
先更新 requirements/database_spec.md
    ↓
再更新 SQL migration
    ↓
再更新 parser / repository / service 代码
    ↓
最后执行 SQL 到 Azure SQL Database
```

如果代码、SQL、README、计划文档与本文档冲突：

1. 数据库尚未建表时，以本文档为准，允许直接重写 SQL 草稿。
2. 数据库已经建表后，以“本文档 + 已执行 migration 历史”为准，新增 migration 修正结构。
3. 临时代码可以为了接口取样先写本地 manifest，但字段含义必须能映射回本文档。

当前事实：

| 项目 | 状态 |
|---|---|
| Azure SQL Database | 已开通 |
| Azure SQL 表 | 尚未创建 |
| Amazon SP-API 连接测试 | 已成功 |
| Reports API 采集闭环 | 本地 Sampling Mode 已实现，已完成 Listing、FBA 库存、销售与流量、Settlement V2 报告下载 |
| 当前 SQL migration | 初始草稿，尚未执行 |
| 当前数据库 spec | 本文件 v1.3 |

---

## 2. 数据库设计目标

第一阶段数据库不是复杂 BI 仓库，而是服务小团队跨境电商运营的轻量数据管道。

目标按优先级分为：

### 2.1 P0：采集和审计闭环

必须能追踪：

1. 提交了什么 Amazon 报告。
2. Amazon 返回的 `reportId`、`reportDocumentId`。
3. 处理状态：`SUBMITTED`、`IN_QUEUE`、`IN_PROGRESS`、`DONE`、`FATAL`、`CANCELLED`。
4. 原始文件保存到了哪里。
5. 文件校验值是什么。
6. 哪个 Job / run 下载了这个文件。
7. 失败原因和重试次数。

### 2.2 P1：真实字段取样和字段目录

必须能维护：

1. 每个 report type 实际返回了哪些列。
2. 每个字段来自哪个 API / report。
3. 字段是否稳定。
4. 字段建议映射到哪个 normalized 表和字段。
5. 字段是否已进入正式 SQL。

### 2.3 P2：标准化业务数据

在拿到真实样例后，再逐步确认：

1. Listing / SKU / ASIN 快照。
2. 库存快照。
3. 销售和流量数据。
4. 财务事件。
5. 广告数据。
6. 促销 / Coupon / Deal 数据。
7. SKU 成本数据。

### 2.4 P3：分析和报表结果

最后再设计和实现：

1. 周度运营快报。
2. 稳定盈亏周报。
3. 月度财务包。
4. 季度会计/报税准备数据包。
5. Excel 文件归档和邮件发送日志。

---

## 3. 数据分层设计

本项目数据库逻辑上分为 5 层。

| 层级 | 名称 | 作用 | 当前是否应建正式表 |
|---|---|---|---|
| L0 | Control 层 | 管理 marketplace、Job 运行、异步报告请求 | 是，第一批稳定 |
| L1 | Raw Archive 层 | 记录原始报告文件、校验值、下载元数据 | 是，第一批稳定 |
| L2 | Sampling / Field Catalog 层 | 记录真实样例字段、字段映射建议和确认状态 | 可以先建，也可以先用本地 markdown/manifest |
| L3 | Normalized 业务层 | 销售、库存、财务、广告、促销、Listing 等标准化表 | 暂不急，取样后确认 |
| L4 | Reporting 层 | 周报/月报/季度包快照、Excel 生成日志 | 暂不急，分析逻辑确认后再建 |

---

## 4. 取样优先开发策略

### 4.1 为什么不先建死所有业务表

Amazon 不同 report type 的字段经常有以下问题：

1. 文档字段和实际文件字段可能不完全一致。
2. 同一个 report type 在不同站点、不同 locale、不同账号状态下字段可能不同。
3. 有些字段名包含空格、大小写、旧字段、Deprecated 字段。
4. 财务、退款、赔偿、清算、仓储费等费用归类需要真实数据后才能定口径。
5. Ads API 的 report 粒度和 attribution 字段需要根据实际下载结果确认。

所以 L3 / L4 表不应现在一次性建完。

### 4.2 本地 Sampling Mode

为了满足“先拿样例，后建正式表”的目标，下一阶段代码开发允许先支持 **本地 Sampling Mode**。

本地 Sampling Mode 不依赖 Azure SQL 表，先把 Amazon 报告流程跑通：

```text
createReport
    ↓
写本地 request manifest
    ↓
getReport 轮询
    ↓
getReportDocument
    ↓
下载 raw file
    ↓
写本地 raw file manifest
    ↓
分析 header / sample rows
    ↓
更新 requirements/database_spec.md
```

建议本地目录：

```text
data/runtime/report_requests.jsonl
data/raw/amazon/sp_api_reports/{marketplace_id}/{report_type}/{yyyy}/{mm}/{dd}/...
data/samples/amazon/{report_type}/...
```

这些目录不应提交 GitHub。`.gitignore` 后续应加入：

```text
data/
reports/raw/
runtime/
```

### 4.3 未来数据库模式

当控制表 SQL 执行后，同一套字段应写入数据库：

```text
amazon_sync_run_log
amazon_report_request
amazon_raw_report_file
amazon_report_field_catalog
```

因此本地 manifest 字段名应尽量与未来数据库字段一致，避免后续迁移重写。

---

## 5. 表设计状态机制

每张表、每个字段在本文档中必须标记状态。

### 5.1 表状态

| 状态 | 含义 |
|---|---|
| `draft` | 仅设计草稿，未拿真实样例，不应执行 SQL |
| `sampling` | 正在通过真实 report/API 样例确认字段 |
| `confirmed` | 结构已确认，可生成 SQL |
| `implemented` | SQL 已执行，代码已按此结构写入 |
| `deprecated` | 不再使用，仅保留历史说明 |

### 5.2 字段状态

| 状态 | 含义 |
|---|---|
| `required_core` | 系统运行必需字段，优先稳定 |
| `observed` | 已在真实样例中出现 |
| `mapped` | 已确认映射到 normalized 表字段 |
| `optional` | 可选字段，可能为空或不稳定 |
| `derived` | 由系统计算得出，不直接来自 Amazon |
| `deferred` | 暂缓入正式表，只保留在 raw_data 或 raw 文件中 |

---

## 6. 当前优先 Marketplace

| 项目 | 值 |
|---|---|
| 第一阶段 Marketplace | Amazon.com |
| Marketplace ID | `ATVPDKIKX0DER` |
| 国家 | US |
| 主要币种 | USD |
| SP-API Region | NA |
| SP-API Endpoint | `https://sellingpartnerapi-na.amazon.com` |

虽然第一阶段只做美国站，所有表仍保留 `marketplace_id` 或 `marketplace` 字段，避免未来扩展加拿大、墨西哥或其他站点时重构。

---

## 7. Amazon Reports API 采集事实

本节只记录对数据库设计有影响的 Reports API 流程事实。

### 7.1 请求参数影响字段设计

`createReport` 至少涉及：

| 参数 | 对数据库的影响 |
|---|---|
| `reportType` | 进入 `report_type` |
| `marketplaceIds` | 进入 `marketplace_id` / `marketplace` |
| `dataStartTime` | 进入 `data_start_time` |
| `dataEndTime` | 进入 `data_end_time` |
| `reportOptions` | 进入 `report_options_json` |

### 7.2 状态机影响字段设计

Reports API 的状态至少需要覆盖：

```text
SUBMITTED：本系统刚提交，Amazon 未必已返回后续状态
IN_QUEUE：Amazon 已排队
IN_PROGRESS：Amazon 正在生成
DONE：Amazon 已完成
FATAL：Amazon 生成失败
CANCELLED：Amazon 取消，可能是无数据或显式取消
```

因此 `amazon_report_request.processing_status` 必须保留这些值。

### 7.3 原始文件保留原则

Report Type Values 中的报告保留期可能因 report type 而不同；如果没有明确保留期，生成报告默认保留 90 天。因此系统下载后必须自行归档 raw file，不能依赖 Amazon 永久保留。

---

## 8. 第一批表：Control + Raw Archive

这批表是下一阶段最重要的稳定设计。即使后续业务字段会变，这些表也应尽早稳定。

### 8.1 `amazon_marketplace`

**表状态：`confirmed`**  
**用途：** 记录可用 marketplace 基础信息。

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `marketplace_id` | `NVARCHAR(50)` | 是 | - | `required_core` | Amazon marketplace ID |
| `marketplace_name` | `NVARCHAR(200)` | 是 | - | `required_core` | 站点名称 |
| `country_code` | `NVARCHAR(10)` | 是 | - | `required_core` | 国家代码 |
| `currency` | `NVARCHAR(10)` | 是 | - | `required_core` | 默认币种 |
| `region` | `NVARCHAR(20)` | 是 | - | `required_core` | SP-API region，如 `NA` |
| `endpoint` | `NVARCHAR(300)` | 是 | - | `required_core` | SP-API endpoint |
| `is_active` | `BIT` | 是 | `1` | `required_core` | 是否启用 |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

唯一键：

```text
marketplace_id
```

---

### 8.2 `amazon_sync_run_log`

**表状态：`confirmed`**  
**用途：** 记录每次脚本、Job、手动取样任务的运行情况。

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `job_name` | `NVARCHAR(120)` | 是 | - | `required_core` | 任务名，如 `submit_report_requests` |
| `job_execution_id` | `NVARCHAR(200)` | 否 | `NULL` | `optional` | 云端 Job 执行 ID 或本地 UUID |
| `run_mode` | `NVARCHAR(50)` | 是 | `local` | `required_core` | `local` / `azure_job` / `github_action` |
| `status` | `NVARCHAR(50)` | 是 | `running` | `required_core` | 运行状态 |
| `started_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 开始时间 |
| `finished_at` | `DATETIME2` | 否 | `NULL` | `optional` | 结束时间 |
| `date_start` | `DATE` | 否 | `NULL` | `optional` | 本次处理业务日期开始 |
| `date_end` | `DATE` | 否 | `NULL` | `optional` | 本次处理业务日期结束 |
| `config_snapshot_json` | `NVARCHAR(MAX)` | 否 | `NULL` | `optional` | 本次运行关键非密钥配置快照 |
| `message` | `NVARCHAR(MAX)` | 否 | `NULL` | `optional` | 简要说明 |
| `error_detail` | `NVARCHAR(MAX)` | 否 | `NULL` | `optional` | 错误详情 |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |

状态枚举：

```text
running
success
failed
partial_success
cancelled
```

推荐索引：

```text
job_name + started_at
status + started_at
```

---

### 8.3 `amazon_report_request`

**表状态：`confirmed`**  
**用途：** 追踪异步报告请求状态。适用于 SP-API Reports，也可扩展 Ads Reporting。

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `marketplace_id` | `NVARCHAR(50)` | 是 | - | `required_core` | Marketplace ID |
| `source_system` | `NVARCHAR(50)` | 是 | - | `required_core` | `sp_api_reports` / `ads_reporting` |
| `report_type` | `NVARCHAR(200)` | 是 | - | `required_core` | Amazon report type 或 Ads report 类型 |
| `report_options_json` | `NVARCHAR(MAX)` | 否 | `NULL` | `optional` | 请求 reportOptions 原样保存 |
| `data_start_time` | `DATETIME2` | 否 | `NULL` | `optional` | 请求数据范围开始。部分 report type 不使用 |
| `data_end_time` | `DATETIME2` | 否 | `NULL` | `optional` | 请求数据范围结束。部分 report type 不使用 |
| `report_id` | `NVARCHAR(300)` | 是 | - | `required_core` | Amazon 返回 report ID |
| `report_document_id` | `NVARCHAR(300)` | 否 | `NULL` | `optional` | DONE 后返回 document ID |
| `processing_status` | `NVARCHAR(50)` | 是 | `SUBMITTED` | `required_core` | Amazon 处理状态 |
| `download_status` | `NVARCHAR(50)` | 是 | `PENDING` | `required_core` | 下载状态 |
| `parse_status` | `NVARCHAR(50)` | 是 | `PENDING` | `required_core` | 解析状态 |
| `requested_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 本系统提交时间 |
| `last_checked_at` | `DATETIME2` | 否 | `NULL` | `optional` | 最近轮询时间 |
| `completed_at` | `DATETIME2` | 否 | `NULL` | `optional` | DONE/FATAL/CANCELLED 时间 |
| `retry_count` | `INT` | 是 | `0` | `required_core` | 重试次数 |
| `source_run_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_sync_run_log.id` |
| `error_message` | `NVARCHAR(MAX)` | 否 | `NULL` | `optional` | 错误信息 |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

推荐唯一键：

```text
marketplace_id + source_system + report_type + report_id
```

说明：`report_id` 是 Amazon 返回的稳定标识；不要只用日期范围去唯一化，因为同一范围可能需要重跑多次取样。

状态枚举：

```text
processing_status: SUBMITTED / IN_QUEUE / IN_PROGRESS / DONE / FATAL / CANCELLED

download_status: PENDING / DOWNLOADING / DOWNLOADED / FAILED / SKIPPED

parse_status: PENDING / PARSING / PARSED / FAILED / NO_DATA / SKIPPED
```

推荐索引：

```text
processing_status + download_status + parse_status + requested_at
source_system + report_type + data_start_time + data_end_time
marketplace_id + report_type + requested_at
```

---

### 8.4 `amazon_raw_report_file`

**表状态：`confirmed`**  
**用途：** 记录下载到本地或 Blob Storage 的原始报告文件。它与 `amazon_report_request` 拆开，避免把文件元数据全部塞进请求表；未来一个请求也可能产生多个派生文件，例如 compressed 原件、解压文件、sample 文件。

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `report_request_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_report_request.id` |
| `marketplace_id` | `NVARCHAR(50)` | 是 | - | `required_core` | Marketplace ID |
| `source_system` | `NVARCHAR(50)` | 是 | - | `required_core` | `sp_api_reports` / `ads_reporting` |
| `report_type` | `NVARCHAR(200)` | 是 | - | `required_core` | 报告类型 |
| `report_id` | `NVARCHAR(300)` | 否 | `NULL` | `optional` | Amazon report ID |
| `report_document_id` | `NVARCHAR(300)` | 否 | `NULL` | `optional` | Amazon document ID |
| `file_role` | `NVARCHAR(50)` | 是 | `raw` | `required_core` | `raw` / `decompressed` / `sample` / `parsed_preview` |
| `storage_backend` | `NVARCHAR(50)` | 是 | `local` | `required_core` | `local` / `azure_blob` |
| `file_path` | `NVARCHAR(1000)` | 是 | - | `required_core` | 本地路径或 Blob path |
| `file_name` | `NVARCHAR(300)` | 是 | - | `required_core` | 文件名 |
| `file_extension` | `NVARCHAR(30)` | 否 | `NULL` | `optional` | `.tsv` / `.csv` / `.json` / `.gz` 等 |
| `content_type` | `NVARCHAR(200)` | 否 | `NULL` | `optional` | HTTP Content-Type |
| `compression_algorithm` | `NVARCHAR(50)` | 否 | `NULL` | `optional` | `GZIP` 等 |
| `encoding` | `NVARCHAR(80)` | 否 | `NULL` | `optional` | 推断或响应头编码，如 `utf-8`、`cp1252` |
| `delimiter` | `NVARCHAR(20)` | 否 | `NULL` | `optional` | `tab` / `comma` / `json` |
| `row_count` | `INT` | 否 | `NULL` | `observed` | 数据行数，不含 header |
| `column_count` | `INT` | 否 | `NULL` | `observed` | 字段列数 |
| `sha256` | `NVARCHAR(100)` | 否 | `NULL` | `required_core` | 文件校验值 |
| `byte_size` | `BIGINT` | 否 | `NULL` | `observed` | 文件大小 |
| `downloaded_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 下载/生成时间 |
| `source_run_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_sync_run_log.id` |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

推荐唯一键：

```text
storage_backend + file_path
```

推荐索引：

```text
source_system + report_type + downloaded_at
report_request_id + file_role
sha256
```

---

### 8.5 `amazon_report_field_catalog`

**表状态：`sampling`**  
**用途：** 记录真实报告文件中观察到的字段清单和后续映射决策。这个表也可以先用 markdown/CSV 维护，等取样稳定后再建表。

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `source_system` | `NVARCHAR(50)` | 是 | - | `required_core` | 数据来源 |
| `report_type` | `NVARCHAR(200)` | 是 | - | `required_core` | 报告类型 |
| `marketplace_id` | `NVARCHAR(50)` | 否 | `NULL` | `optional` | Marketplace ID；字段跨站一致时可为空 |
| `sample_file_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_raw_report_file.id` |
| `field_position` | `INT` | 否 | `NULL` | `observed` | 字段在文件中的列顺序 |
| `source_field_name` | `NVARCHAR(300)` | 是 | - | `observed` | 原始字段名 |
| `normalized_field_name` | `NVARCHAR(200)` | 否 | `NULL` | `mapped` | 建议标准字段名 |
| `target_table` | `NVARCHAR(200)` | 否 | `NULL` | `mapped` | 建议进入哪张 normalized 表 |
| `target_column` | `NVARCHAR(200)` | 否 | `NULL` | `mapped` | 建议进入哪个字段 |
| `data_type_suggestion` | `NVARCHAR(100)` | 否 | `NULL` | `mapped` | 建议类型，如 int/decimal/date/string |
| `nullable_observed` | `BIT` | 否 | `NULL` | `observed` | 样例中是否出现空值 |
| `sample_values_json` | `NVARCHAR(MAX)` | 否 | `NULL` | `observed` | 少量脱敏样例值 |
| `mapping_status` | `NVARCHAR(50)` | 是 | `observed` | `required_core` | 字段映射状态 |
| `remark` | `NVARCHAR(MAX)` | 否 | `NULL` | `optional` | 备注 |
| `first_seen_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 首次发现时间 |
| `last_seen_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 最近发现时间 |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

`mapping_status` 枚举：

```text
observed
mapped
confirmed
deferred
ignored
```

推荐唯一键：

```text
source_system + report_type + marketplace_id + source_field_name
```

注意：SQL Server 中包含 NULL 的唯一约束有特殊行为；如果实现时允许 `marketplace_id` 为空，需使用过滤索引或在 repository 层统一用 `GLOBAL` 代替空值。

---

## 9. 第二批表：Normalized 业务层草案

以下表当前只作为方向设计。执行 SQL 前必须至少拿到一个真实样例，并在本文档中把表状态从 `draft/sampling` 改为 `confirmed`。

| 表名 | 表状态 | 第一数据来源候选 | 说明 |
|---|---|---|---|
| `amazon_listing_snapshot` | `sampling` | `GET_MERCHANT_LISTINGS_ALL_DATA` / `GET_FLAT_FILE_OPEN_LISTINGS_DATA` | Listing、SKU、ASIN、价格、状态、库存数量等 |
| `amazon_inventory_daily` | `sampling` | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | FBA 库存快照，可售、预留、不可售、入库中等字段 |
| `amazon_sales_traffic_daily` | `sampling` | `GET_SALES_AND_TRAFFIC_REPORT` | 日期维度销售额、订单数、件数、退款、Sessions、Page Views、转化率等 |
| `amazon_sales_traffic_asin_daily` | `sampling` | `GET_SALES_AND_TRAFFIC_REPORT` | ASIN 维度销售与流量；7 天窗口样例已返回 PARENT ASIN 聚合行 |
| `amazon_settlement_transaction` | `sampling` | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | 结算报告明细行，作为利润费用侧第一数据源；已发现并下载 8 份真实样例 |
| `amazon_order_item` | `sampling` | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | 订单/行项目维度收入、数量、订单状态、促销折扣 |
| `amazon_return_request` | `sampling` | `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` | 退货请求、RMA、原因、状态；当前样例为 header-only |
| `amazon_fba_reimbursement` | `sampling` | `GET_FBA_REIMBURSEMENTS_DATA` | FBA 赔偿、case、原因、现金/库存赔偿数量 |
| `amazon_fba_fee_preview` | `sampling` | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | SKU/ASIN 维度 referral fee 与 FBA fulfillment fee 预估 |
| `amazon_inventory_planning_daily` | `sampling` | `GET_FBA_INVENTORY_PLANNING_DATA` | 库龄、库存健康、周转、冗余和建议动作 |
| `amazon_inventory_ledger_summary_daily` | `sampling` | `GET_LEDGER_SUMMARY_VIEW_DATA` | FBA 库存流水汇总，解释库存变化和差异 |
| `amazon_finance_event` | `draft` | Settlement reports / Finances API | 费用、退款、赔偿、仓储费、月租等的统一归类层，需先取样分类 |
| `amazon_ads_daily` | `draft` | Amazon Ads Reporting | Sponsored Products 广告表现，需确认 profile_id 和报表粒度 |
| `amazon_promotion_performance` | `sampling` | `GET_PROMOTION_PERFORMANCE_REPORT` | Deal/Promotion 活动主表，记录活动总体曝光、销售件数和销售额等运营效果 |
| `amazon_promotion_product_performance` | `sampling` | `GET_PROMOTION_PERFORMANCE_REPORT` | Promotion 关联 ASIN 明细表，记录活动商品维度表现 |
| `amazon_coupon_performance` | `sampling` | `GET_COUPON_PERFORMANCE_REPORT` | Coupon 主表，记录预算、领取、兑换、折扣、销售等运营效果 |
| `amazon_coupon_asin` | `sampling` | `GET_COUPON_PERFORMANCE_REPORT` | Coupon 关联 ASIN 明细表 |
| `amazon_sku_cost` | `confirmed` | 人工维护 / Excel 导入 | 采购、头程、包装、其他单位成本；可较早建表 |

### 9.1 Normalized 表通用字段要求

所有 L3 normalized 表原则上都要包含：

```text
id
marketplace_id
source_system
source_report_request_id
source_raw_file_id
source_run_id
raw_data
created_at
updated_at
```

其中：

| 字段 | 说明 |
|---|---|
| `source_report_request_id` | 追溯到异步请求 |
| `source_raw_file_id` | 追溯到原始文件 |
| `source_run_id` | 追溯到 Job 运行 |
| `raw_data` | 保存该行原始 JSON，方便排查 parser 问题 |

### 9.2 唯一键原则

业务表必须支持重复回刷，所以不能只 insert。

原则：

```text
能用 Amazon 原始唯一 ID，就用原始唯一 ID。
没有原始唯一 ID，就使用业务键。
业务键仍不稳定时，生成 source_row_hash。
```

推荐保留字段：

```text
source_row_hash NVARCHAR(100)
```

用于从原始行生成 SHA256，避免重复写入。


### 9.3 `amazon_listing_snapshot`

**表状态：`sampling`**  
**第一数据来源：** `GET_MERCHANT_LISTINGS_ALL_DATA`  
**样例记录：** `requirements/data_samples/GET_MERCHANT_LISTINGS_ALL_DATA.md`  
**用途：** 保存每次 Listing 报告解析后的 SKU / ASIN / Listing / 价格 / 状态快照。

第一份真实样例结论：

| 项目 | 结论 |
|---|---|
| report_type | `GET_MERCHANT_LISTINGS_ALL_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| 文件格式 | tab-delimited flat file |
| 样例行数 | 6 行数据 |
| 样例字段数 | 29 个字段 |
| 适合进入本表 | Listing 基础信息、SKU、ASIN、价格、状态、履约渠道 |
| 不适合作为库存唯一来源 | `quantity`、`pending-quantity` 在本次 FBA 样例中均为空 |

#### 9.3.1 字段设计草案

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 来源字段 / 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `marketplace_id` | `NVARCHAR(50)` | 是 | - | `required_core` | Marketplace ID |
| `snapshot_date` | `DATE` | 是 | - | `derived` | 本次下载/解析日期；后续可改为报告业务日期 |
| `listing_id` | `NVARCHAR(100)` | 是 | - | `observed` | `listing-id` |
| `seller_sku` | `NVARCHAR(200)` | 是 | - | `observed` | `seller-sku` |
| `asin` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | 优先取 `asin1` |
| `product_id` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `product-id` |
| `product_id_type` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `product-id-type`，Amazon 原始枚举码 |
| `item_name` | `NVARCHAR(1000)` | 否 | `NULL` | `observed` | `item-name` |
| `item_description` | `NVARCHAR(MAX)` | 否 | `NULL` | `observed` | `item-description` |
| `price` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `price` |
| `currency` | `NVARCHAR(10)` | 否 | `NULL` | `derived` | 第一阶段美国站默认为 `USD` |
| `quantity` | `INT` | 否 | `NULL` | `observed` | `quantity`；FBA 样例为空，不作为库存主口径 |
| `pending_quantity` | `INT` | 否 | `NULL` | `observed` | `pending-quantity`；FBA 样例为空 |
| `open_date_raw` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `open-date` 原始字符串，含时区缩写 |
| `open_date_utc` | `DATETIME2` | 否 | `NULL` | `derived` | 后续确认时区解析规则后再填充 |
| `item_is_marketplace` | `BIT` | 否 | `NULL` | `observed` | `item-is-marketplace`，`y/n` 转换 |
| `item_condition` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `item-condition`，Amazon 原始枚举码 |
| `fulfillment_channel` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `fulfillment-channel`，如 `AMAZON_NA` |
| `merchant_shipping_group` | `NVARCHAR(200)` | 否 | `NULL` | `observed` | `merchant-shipping-group` |
| `status` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `status`，如 `Active` / `Inactive` / `Incomplete` |
| `source_system` | `NVARCHAR(50)` | 是 | `sp_api_reports` | `required_core` | 数据来源 |
| `source_report_type` | `NVARCHAR(200)` | 是 | - | `required_core` | `GET_MERCHANT_LISTINGS_ALL_DATA` |
| `source_report_id` | `NVARCHAR(300)` | 否 | `NULL` | `required_core` | Amazon report ID |
| `source_report_request_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_report_request.id` |
| `source_raw_file_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_raw_report_file.id` |
| `source_run_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_sync_run_log.id` |
| `source_row_hash` | `NVARCHAR(100)` | 是 | - | `required_core` | 原始行 JSON 的 SHA256，用于回刷去重 |
| `raw_data` | `NVARCHAR(MAX)` | 是 | - | `required_core` | 单行原始 JSON |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

#### 9.3.2 暂缓进入正式列的字段

以下字段在第一份样例中为空或暂时价值不高，先保留在 `raw_data` 和 raw file 中：

```text
image-url
zshop-shipping-fee
item-note
zshop-category1
zshop-browse-path
zshop-storefront-feature
asin2
asin3
will-ship-internationally
expedited-shipping
zshop-boldface
bid-for-featured-placement
add-delete
```

#### 9.3.3 唯一键草案

推荐唯一键：

```text
marketplace_id + source_report_type + listing_id + seller_sku + snapshot_date
```

说明：

1. `listing-id` 是本报告中观察到的 Listing 维度标识。
2. `seller_sku` 仍保留在唯一键中，便于与后续库存、销售、成本表关联。
3. `snapshot_date` 保证同一 Listing 可以保留多日快照。
4. 如果未来发现 `listing-id` 在某些报告中不稳定，则用 `source_row_hash` 辅助去重。

#### 9.3.4 Parser 实现状态

当前已新增本地 parser 草案：

```text
src/seller_data_pipeline/parsers/amazon/listings_all_data_parser.py
```

Parser 当前只做标准化内存记录，不写数据库。等本表字段从 `sampling` 升级为 `confirmed` 后，再实现 repository / upsert SQL。

---

### 9.4 `amazon_inventory_daily`

**表状态：`sampling`**  
**第一数据来源：** `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA`  
**样例记录：** `requirements/data_samples/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA.md`  
**用途：** 保存每次 FBA 库存报告解析后的 SKU / FNSKU / ASIN 库存快照。

第二份真实样例结论：

| 项目 | 结论 |
|---|---|
| report_type | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| 文件格式 | tab-delimited flat file |
| 样例编码 | `cp1252` |
| 样例行数 | 5 行数据 |
| 样例字段数 | 22 个字段 |
| 适合进入本表 | FBA 可售、仓内、预留、不可售、入库中、researching 等库存字段 |
| 第一版主库存口径 | `afn-fulfillable-quantity` |
| 辅助解释字段 | `afn-total-quantity`、`afn-reserved-quantity`、`afn-unsellable-quantity`、`afn-warehouse-quantity` |

#### 9.4.1 字段设计草案

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 来源字段 / 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `marketplace_id` | `NVARCHAR(50)` | 是 | - | `required_core` | Marketplace ID |
| `snapshot_date` | `DATE` | 是 | - | `derived` | 本次下载/解析日期；第一版作为库存快照日期 |
| `seller_sku` | `NVARCHAR(200)` | 是 | - | `observed` | `sku` |
| `fnsku` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `fnsku` |
| `asin` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `asin` |
| `product_name` | `NVARCHAR(1000)` | 否 | `NULL` | `observed` | `product-name` |
| `condition` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `condition`，如 `New` |
| `your_price` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `your-price` |
| `currency` | `NVARCHAR(10)` | 否 | `NULL` | `derived` | 第一阶段美国站默认为 `USD` |
| `mfn_listing_exists` | `BIT` | 否 | `NULL` | `observed` | `mfn-listing-exists`，`Yes/No` 转换 |
| `mfn_fulfillable_quantity` | `INT` | 否 | `NULL` | `observed` | `mfn-fulfillable-quantity`，本次样例为空 |
| `afn_listing_exists` | `BIT` | 否 | `NULL` | `observed` | `afn-listing-exists`，`Yes/No` 转换 |
| `afn_warehouse_quantity` | `INT` | 否 | `NULL` | `observed` | `afn-warehouse-quantity` |
| `afn_fulfillable_quantity` | `INT` | 否 | `NULL` | `observed` | `afn-fulfillable-quantity`，第一版可售库存主口径 |
| `afn_unsellable_quantity` | `INT` | 否 | `NULL` | `observed` | `afn-unsellable-quantity` |
| `afn_reserved_quantity` | `INT` | 否 | `NULL` | `observed` | `afn-reserved-quantity` |
| `afn_total_quantity` | `INT` | 否 | `NULL` | `observed` | `afn-total-quantity` |
| `per_unit_volume` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `per-unit-volume` |
| `afn_inbound_working_quantity` | `INT` | 否 | `NULL` | `observed` | `afn-inbound-working-quantity` |
| `afn_inbound_shipped_quantity` | `INT` | 否 | `NULL` | `observed` | `afn-inbound-shipped-quantity` |
| `afn_inbound_receiving_quantity` | `INT` | 否 | `NULL` | `observed` | `afn-inbound-receiving-quantity` |
| `afn_researching_quantity` | `INT` | 否 | `NULL` | `observed` | `afn-researching-quantity` |
| `afn_reserved_future_supply` | `INT` | 否 | `NULL` | `observed` | `afn-reserved-future-supply` |
| `afn_future_supply_buyable` | `INT` | 否 | `NULL` | `observed` | `afn-future-supply-buyable` |
| `store` | `NVARCHAR(200)` | 否 | `NULL` | `observed` | `store`，本次样例为空 |
| `source_system` | `NVARCHAR(50)` | 是 | `sp_api_reports` | `required_core` | 数据来源 |
| `source_report_type` | `NVARCHAR(200)` | 是 | - | `required_core` | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` |
| `source_report_id` | `NVARCHAR(300)` | 否 | `NULL` | `required_core` | Amazon report ID |
| `source_report_request_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_report_request.id` |
| `source_raw_file_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_raw_report_file.id` |
| `source_run_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_sync_run_log.id` |
| `source_row_hash` | `NVARCHAR(100)` | 是 | - | `required_core` | 原始行 JSON 的 SHA256，用于回刷去重 |
| `raw_data` | `NVARCHAR(MAX)` | 是 | - | `required_core` | 单行原始 JSON |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

#### 9.4.2 第一版库存口径

第一版运营库存建议采用：

```text
available_inventory = afn_fulfillable_quantity
warehouse_inventory = afn_warehouse_quantity
total_inventory = afn_total_quantity
reserved_inventory = afn_reserved_quantity
unsellable_inventory = afn_unsellable_quantity
inbound_inventory = afn_inbound_working_quantity
                  + afn_inbound_shipped_quantity
                  + afn_inbound_receiving_quantity
```

注意：

1. `afn-fulfillable-quantity` 是 FBA 当前可履约库存，更适合周报中的“可售库存”。
2. `afn-total-quantity` 不是可售库存，它包含预留、不可售等状态。
3. `mfn-fulfillable-quantity` 本次样例为空，但如果未来有自发货 SKU，不能直接删除字段。
4. 本报告可以补充 `fnsku`，Listing 报告不能提供该字段。

#### 9.4.3 唯一键草案

推荐唯一键：

```text
marketplace_id + source_report_type + seller_sku + fnsku + snapshot_date
```

说明：

1. `seller_sku` 是后续成本、销售、广告归集的主关联键。
2. `fnsku` 是 FBA 库存维度的重要标识，同一 SKU 未来理论上可能因库存/贴标变化出现不同 FNSKU。
3. `asin` 保留为辅助关联字段，不建议单独作为唯一键。
4. 如果 `fnsku` 为空，则 upsert 时需要降级使用 `source_row_hash` 或 `seller_sku + asin + condition`。

#### 9.4.4 Parser 实现状态

当前已新增本地 parser 草案：

```text
src/seller_data_pipeline/parsers/amazon/fba_inventory_parser.py
```

Parser 当前只做标准化内存记录，不写数据库。等本表字段从 `sampling` 升级为 `confirmed` 后，再实现 repository / upsert SQL。

---


### 9.5 `amazon_sales_traffic_daily`

**表状态：`sampling`**  
**第一数据来源：** `GET_SALES_AND_TRAFFIC_REPORT`  
**样例记录：** `requirements/data_samples/GET_SALES_AND_TRAFFIC_REPORT.md`  
**用途：** 保存 Business Reports 销售与流量报告中的日期维度运营指标，用于周报、月报、转化率分析和销售趋势分析。

第三、四份真实销售与流量样例结论：

| 项目 | 结论 |
|---|---|
| report_type | `GET_SALES_AND_TRAFFIC_REPORT` |
| marketplace_id | `ATVPDKIKX0DER` |
| 文件格式 | JSON |
| 样例编码 | `utf-8-sig` |
| reportOptions.dateGranularity | `DAY` |
| reportOptions.asinGranularity | `PARENT` |
| 单日样例 `salesAndTrafficByDate` | 1 行 |
| 单日样例 `salesAndTrafficByAsin` | 0 行 |
| 7 天窗口样例 `salesAndTrafficByDate` | 6 行 |
| 7 天窗口样例 `salesAndTrafficByAsin` | 1 行，PARENT 粒度 |
| 7 天窗口样例字段路径数 | 94 个 |
| 适合进入本表 | 日期、销售额、订单数、销售件数、退款、Page Views、Sessions、转化率、Buy Box 百分比等 |
| 不适合直接做利润 | 本报告没有 Amazon 费用、FBA fee、广告费、促销费、采购成本 |

#### 9.5.1 字段设计草案

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 来源字段 / 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `marketplace_id` | `NVARCHAR(50)` | 是 | - | `required_core` | Marketplace ID |
| `report_date` | `DATE` | 是 | - | `observed` | `salesAndTrafficByDate[].date` |
| `date_granularity` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `reportSpecification.reportOptions.dateGranularity`，本次为 `DAY` |
| `asin_granularity` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `reportSpecification.reportOptions.asinGranularity`，本次为 `PARENT` |
| `ordered_product_sales_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByDate.orderedProductSales.amount` |
| `ordered_product_sales_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByDate.orderedProductSales.currencyCode` |
| `ordered_product_sales_b2b_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByDate.orderedProductSalesB2B.amount` |
| `ordered_product_sales_b2b_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByDate.orderedProductSalesB2B.currencyCode` |
| `units_ordered` | `INT` | 否 | `NULL` | `observed` | `salesByDate.unitsOrdered` |
| `units_ordered_b2b` | `INT` | 否 | `NULL` | `observed` | `salesByDate.unitsOrderedB2B` |
| `total_order_items` | `INT` | 否 | `NULL` | `observed` | `salesByDate.totalOrderItems` |
| `total_order_items_b2b` | `INT` | 否 | `NULL` | `observed` | `salesByDate.totalOrderItemsB2B` |
| `average_sales_per_order_item_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByDate.averageSalesPerOrderItem.amount` |
| `average_sales_per_order_item_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByDate.averageSalesPerOrderItem.currencyCode` |
| `average_sales_per_order_item_b2b_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByDate.averageSalesPerOrderItemB2B.amount` |
| `average_sales_per_order_item_b2b_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByDate.averageSalesPerOrderItemB2B.currencyCode` |
| `average_units_per_order_item` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `salesByDate.averageUnitsPerOrderItem` |
| `average_units_per_order_item_b2b` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `salesByDate.averageUnitsPerOrderItemB2B` |
| `average_selling_price_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByDate.averageSellingPrice.amount` |
| `average_selling_price_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByDate.averageSellingPrice.currencyCode` |
| `average_selling_price_b2b_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByDate.averageSellingPriceB2B.amount` |
| `average_selling_price_b2b_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByDate.averageSellingPriceB2B.currencyCode` |
| `units_refunded` | `INT` | 否 | `NULL` | `observed` | `salesByDate.unitsRefunded` |
| `refund_rate` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `salesByDate.refundRate` |
| `claims_granted` | `INT` | 否 | `NULL` | `observed` | `salesByDate.claimsGranted` |
| `claims_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByDate.claimsAmount.amount` |
| `claims_amount_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByDate.claimsAmount.currencyCode` |
| `shipped_product_sales_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByDate.shippedProductSales.amount` |
| `shipped_product_sales_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByDate.shippedProductSales.currencyCode` |
| `units_shipped` | `INT` | 否 | `NULL` | `observed` | `salesByDate.unitsShipped` |
| `orders_shipped` | `INT` | 否 | `NULL` | `observed` | `salesByDate.ordersShipped` |
| `browser_page_views` | `INT` | 否 | `NULL` | `observed` | `trafficByDate.browserPageViews` |
| `mobile_app_page_views` | `INT` | 否 | `NULL` | `observed` | `trafficByDate.mobileAppPageViews` |
| `page_views` | `INT` | 否 | `NULL` | `observed` | `trafficByDate.pageViews` |
| `browser_sessions` | `INT` | 否 | `NULL` | `observed` | `trafficByDate.browserSessions` |
| `mobile_app_sessions` | `INT` | 否 | `NULL` | `observed` | `trafficByDate.mobileAppSessions` |
| `sessions` | `INT` | 否 | `NULL` | `observed` | `trafficByDate.sessions` |
| `buy_box_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByDate.buyBoxPercentage` |
| `order_item_session_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByDate.orderItemSessionPercentage` |
| `unit_session_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByDate.unitSessionPercentage` |
| `average_offer_count` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByDate.averageOfferCount` |
| `average_parent_items` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByDate.averageParentItems` |
| `feedback_received` | `INT` | 否 | `NULL` | `observed` | `trafficByDate.feedbackReceived` |
| `negative_feedback_received` | `INT` | 否 | `NULL` | `observed` | `trafficByDate.negativeFeedbackReceived` |
| `received_negative_feedback_rate` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByDate.receivedNegativeFeedbackRate` |
| `source_system` | `NVARCHAR(50)` | 是 | `sp_api_reports` | `required_core` | 数据来源 |
| `source_report_type` | `NVARCHAR(200)` | 是 | - | `required_core` | `GET_SALES_AND_TRAFFIC_REPORT` |
| `source_report_id` | `NVARCHAR(300)` | 否 | `NULL` | `required_core` | Amazon report ID |
| `source_report_request_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_report_request.id` |
| `source_raw_file_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_raw_report_file.id` |
| `source_run_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_sync_run_log.id` |
| `source_row_hash` | `NVARCHAR(100)` | 是 | - | `required_core` | 日期行原始 JSON 的 SHA256，用于回刷去重 |
| `raw_data` | `NVARCHAR(MAX)` | 是 | - | `required_core` | 单行原始 JSON |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

#### 9.5.2 第一版销售与流量口径

第一版运营分析建议采用：

```text
ordered_sales = ordered_product_sales_amount
ordered_units = units_ordered
ordered_items = total_order_items
shipped_sales = shipped_product_sales_amount
shipped_units = units_shipped
traffic_sessions = sessions
traffic_page_views = page_views
conversion_rate = unit_session_percentage
refund_units = units_refunded
refund_rate = refund_rate
```

注意：

1. 本表是“销售与流量”数据，不是最终利润表。
2. 费用、退款金额、FBA fee、广告费、促销费需要后续 Finances / Ads / Promotion 数据补齐。
3. 7 天窗口样例已经验证非零销售、退款、B2B 销售、流量指标均能返回。
4. `salesAndTrafficByAsin` 已返回 PARENT ASIN 聚合行，因此 ASIN 维度可进入 `sampling` 状态，但还不能升级为 `confirmed`。

#### 9.5.3 唯一键草案

推荐唯一键：

```text
marketplace_id + source_report_type + report_date + date_granularity + asin_granularity
```

说明：

1. 日期维度报告本身没有 Amazon 原始唯一 ID。
2. 同一日期、同一 marketplace、同一 granularity 应只有一条日期汇总记录。
3. 如果未来支持多种 `reportOptions`，granularity 必须进入唯一键，避免 DAY/WEEK/MONTH 混写。

#### 9.5.4 Parser 实现状态

当前已新增本地 parser 草案：

```text
src/seller_data_pipeline/parsers/amazon/sales_report_parser.py
```

Parser 当前只做标准化内存记录，不写数据库。等本表字段从 `sampling` 升级为 `confirmed` 后，再实现 repository / upsert SQL。

#### 9.5.5 后续待补样例

需要继续补充：

1. 更长日期窗口，例如最近 7 天或最近 30 天，验证多日记录和非零销售数据。
2. 继续测试 `asinGranularity=CHILD` 或后续 reportOptions 支持情况，确认是否需要 child ASIN 维度。
3. 与 Finances API 对齐，确认销售额和费用、退款金额、赔偿、清算的关系。


### 9.6 `amazon_sales_traffic_asin_daily`

**表状态：`sampling`**  
**第一数据来源：** `GET_SALES_AND_TRAFFIC_REPORT`  
**样例记录：** `requirements/data_samples/GET_SALES_AND_TRAFFIC_REPORT.md`  
**用途：** 保存 Business Reports 销售与流量报告中的 ASIN 维度聚合指标，用于父体/子体商品表现分析。

7 天窗口真实样例结论：

| 项目 | 结论 |
|---|---|
| report_type | `GET_SALES_AND_TRAFFIC_REPORT` |
| reportOptions.dateGranularity | `DAY` |
| reportOptions.asinGranularity | `PARENT` |
| `salesAndTrafficByAsin` | 1 行 |
| ASIN 维度 | 当前样例为 `parentAsin`，`childAsin` 未出现 |
| 适合进入本表 | parent ASIN、销售额、订单数、销售件数、Sessions、Page Views、各类百分比、Buy Box 百分比 |
| 不足 | 当前只有一个父体 ASIN 样例；还需确认 CHILD 粒度是否可用 |

#### 9.6.1 字段设计草案

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 来源字段 / 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `marketplace_id` | `NVARCHAR(50)` | 是 | - | `required_core` | Marketplace ID |
| `report_start_date` | `DATE` | 否 | `NULL` | `observed` | `reportSpecification.dataStartTime` |
| `report_end_date` | `DATE` | 否 | `NULL` | `observed` | `reportSpecification.dataEndTime` |
| `date_granularity` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `reportSpecification.reportOptions.dateGranularity` |
| `asin_granularity` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `reportSpecification.reportOptions.asinGranularity` |
| `parent_asin` | `NVARCHAR(50)` | 否 | `NULL` | `observed` | `salesAndTrafficByAsin[].parentAsin` |
| `child_asin` | `NVARCHAR(50)` | 否 | `NULL` | `reserved` | `salesAndTrafficByAsin[].childAsin`，当前样例未出现 |
| `ordered_product_sales_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByAsin.orderedProductSales.amount` |
| `ordered_product_sales_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByAsin.orderedProductSales.currencyCode` |
| `ordered_product_sales_b2b_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `salesByAsin.orderedProductSalesB2B.amount` |
| `ordered_product_sales_b2b_currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `salesByAsin.orderedProductSalesB2B.currencyCode` |
| `units_ordered` | `INT` | 否 | `NULL` | `observed` | `salesByAsin.unitsOrdered` |
| `units_ordered_b2b` | `INT` | 否 | `NULL` | `observed` | `salesByAsin.unitsOrderedB2B` |
| `total_order_items` | `INT` | 否 | `NULL` | `observed` | `salesByAsin.totalOrderItems` |
| `total_order_items_b2b` | `INT` | 否 | `NULL` | `observed` | `salesByAsin.totalOrderItemsB2B` |
| `browser_page_views` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.browserPageViews` |
| `browser_page_views_b2b` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.browserPageViewsB2B` |
| `browser_page_views_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.browserPageViewsPercentage` |
| `browser_page_views_percentage_b2b` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.browserPageViewsPercentageB2B` |
| `mobile_app_page_views` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.mobileAppPageViews` |
| `mobile_app_page_views_b2b` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.mobileAppPageViewsB2B` |
| `mobile_app_page_views_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.mobileAppPageViewsPercentage` |
| `mobile_app_page_views_percentage_b2b` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.mobileAppPageViewsPercentageB2B` |
| `page_views` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.pageViews` |
| `page_views_b2b` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.pageViewsB2B` |
| `page_views_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.pageViewsPercentage` |
| `page_views_percentage_b2b` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.pageViewsPercentageB2B` |
| `browser_sessions` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.browserSessions` |
| `browser_sessions_b2b` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.browserSessionsB2B` |
| `browser_session_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.browserSessionPercentage` |
| `browser_session_percentage_b2b` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.browserSessionPercentageB2B` |
| `mobile_app_sessions` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.mobileAppSessions` |
| `mobile_app_sessions_b2b` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.mobileAppSessionsB2B` |
| `mobile_app_session_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.mobileAppSessionPercentage` |
| `mobile_app_session_percentage_b2b` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.mobileAppSessionPercentageB2B` |
| `sessions` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.sessions` |
| `sessions_b2b` | `INT` | 否 | `NULL` | `observed` | `trafficByAsin.sessionsB2B` |
| `session_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.sessionPercentage` |
| `session_percentage_b2b` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.sessionPercentageB2B` |
| `buy_box_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.buyBoxPercentage` |
| `buy_box_percentage_b2b` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.buyBoxPercentageB2B` |
| `unit_session_percentage` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.unitSessionPercentage` |
| `unit_session_percentage_b2b` | `DECIMAL(18,6)` | 否 | `NULL` | `observed` | `trafficByAsin.unitSessionPercentageB2B` |
| `source_system` | `NVARCHAR(50)` | 是 | `sp_api_reports` | `required_core` | 数据来源 |
| `source_report_type` | `NVARCHAR(200)` | 是 | - | `required_core` | `GET_SALES_AND_TRAFFIC_REPORT` |
| `source_report_id` | `NVARCHAR(300)` | 否 | `NULL` | `required_core` | Amazon report ID |
| `source_report_request_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_report_request.id` |
| `source_raw_file_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_raw_report_file.id` |
| `source_run_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_sync_run_log.id` |
| `source_row_hash` | `NVARCHAR(100)` | 是 | - | `required_core` | ASIN 行原始 JSON 的 SHA256，用于回刷去重 |
| `raw_data` | `NVARCHAR(MAX)` | 是 | - | `required_core` | 单行原始 JSON |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

#### 9.6.2 唯一键草案

推荐唯一键：

```text
marketplace_id + source_report_type + report_start_date + report_end_date + asin_granularity + parent_asin
```

说明：

1. 当前样例为 PARENT 粒度，因此先用 `parent_asin` 作为业务键核心。
2. 如果后续支持 CHILD 粒度，应把 `child_asin` 纳入唯一键或拆分粒度处理。
3. 因为本表是报告窗口聚合，不是每日逐 ASIN 行，必须保留 report_start_date / report_end_date。
4. 如果后续需要每日 ASIN 表，应尝试 reportOptions 是否可返回更细粒度。

#### 9.6.3 Parser 实现状态

当前 parser 已能解析 `salesAndTrafficByAsin` 中观察到的 PARENT ASIN 聚合字段：

```text
src/seller_data_pipeline/parsers/amazon/sales_report_parser.py
```

Parser 当前只做标准化内存记录，不写数据库。等本表字段从 `sampling` 升级为 `confirmed` 后，再实现 repository / upsert SQL。

---

### 9.7 `amazon_settlement_transaction`

**表状态：`sampling`**  
**第一数据来源：** `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2`  
**样例记录：** `requirements/data_samples/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.md`  
**用途：** 保存 Amazon 结算报告中的逐行财务交易明细，作为退款、平台费、FBA fee、广告费、赔偿、清算、促销抵扣、仓储费、月租等利润费用侧的第一来源。

重要采集事实：

1. Settlement reports 不是普通 requestable report，不能用 `createReport` 主动生成。
2. 需要通过 Reports API `getReports` 按 `reportTypes=GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2`、`processingStatuses=DONE` 发现 Amazon 自动生成的报告。
3. 本次 89 天窗口发现并下载 8 份报告，合计 4,911 行；每份报告第一行通常是 settlement summary 行。
4. Summary 行包含 `settlement-start-date`、`settlement-end-date`、`deposit-date`、`total-amount`、`currency`；后续交易明细行这些列通常为空。
5. Parser 必须把 summary 元数据向下继承到交易明细行，否则大部分交易会缺少币种和结算周期。
6. Flat File V2 把金额统一收敛到 `amount-type`、`amount-description`、`amount` 三列，适合用字典做费用分类。
7. 本次样例已出现广告费、Coupon fee、Deal fee、Storage Fee、Subscription Fee、FBA Inbound Placement Service Fee、Inventory Reimbursement、Liquidations 等利润关键类型。

#### 9.7.1 字段设计草案

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 来源字段 / 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `marketplace_id` | `NVARCHAR(50)` | 是 | - | `required_core` | Marketplace ID |
| `settlement_id` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `settlement-id` |
| `settlement_start_date_raw` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `settlement-start-date`；parser 从 summary 行继承到明细行 |
| `settlement_end_date_raw` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `settlement-end-date`；parser 从 summary 行继承到明细行 |
| `deposit_date_raw` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `deposit-date`；parser 从 summary 行继承到明细行 |
| `total_amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `total-amount`；结算总额，parser 从 summary 行继承到明细行，用于 reconciliation |
| `currency` | `NVARCHAR(10)` | 否 | `NULL` | `observed` | `currency`；parser 从 summary 行继承到明细行 |
| `is_settlement_summary` | `BIT` | 是 | `0` | `mapped` | 是否为 settlement summary 行；summary 行不直接参与利润明细汇总 |
| `transaction_type` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `transaction-type`，如 Order / Refund / ServiceFee / AmazonFees / Liquidations |
| `order_id` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `order-id` |
| `merchant_order_id` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `merchant-order-id` |
| `adjustment_id` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `adjustment-id` |
| `shipment_id` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `shipment-id` |
| `marketplace_name` | `NVARCHAR(200)` | 否 | `NULL` | `observed` | `marketplace-name` |
| `amount_type` | `NVARCHAR(200)` | 否 | `NULL` | `observed` | `amount-type`，费用大类 |
| `amount_description` | `NVARCHAR(300)` | 否 | `NULL` | `observed` | `amount-description`，费用细项 |
| `amount` | `DECIMAL(18,4)` | 否 | `NULL` | `observed` | `amount`，行级金额；利润计算主要使用该字段 |
| `amount_category` | `NVARCHAR(100)` | 是 | - | `mapped` | parser 第一版分类，如 product_sales / fba_fulfillment_fee / advertising_fee / refund_revenue |
| `profit_bucket` | `NVARCHAR(100)` | 是 | - | `mapped` | 运营利润归集桶，如 revenue / amazon_fee / fba_fee / promotion_cost / advertising_cost / reimbursement / tax_passthrough |
| `fulfillment_id` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `fulfillment-id` |
| `posted_date_raw` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `posted-date` 原始字符串；样例中存在 yyyy-mm-dd 与 dd.mm.yyyy 两类格式 |
| `posted_date_time_raw` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `posted-date-time` 原始字符串 |
| `order_item_code` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `order-item-code` |
| `merchant_order_item_id` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `merchant-order-item-id` |
| `merchant_adjustment_item_id` | `NVARCHAR(100)` | 否 | `NULL` | `observed` | `merchant-adjustment-item-id` |
| `seller_sku` | `NVARCHAR(200)` | 否 | `NULL` | `observed` | `sku`；费用类行可能为空 |
| `quantity_purchased` | `INT` | 否 | `NULL` | `observed` | `quantity-purchased` |
| `promotion_id` | `NVARCHAR(300)` | 否 | `NULL` | `observed` | `promotion-id`；样例中 Coupon / Deal fee 行可能为空 |
| `source_system` | `NVARCHAR(50)` | 是 | `sp_api_reports` | `required_core` | 数据来源 |
| `source_report_type` | `NVARCHAR(200)` | 是 | - | `required_core` | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` |
| `source_report_id` | `NVARCHAR(300)` | 否 | `NULL` | `required_core` | Amazon report ID |
| `source_report_request_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_report_request.id` |
| `source_raw_file_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_raw_report_file.id` |
| `source_run_id` | `BIGINT` | 否 | `NULL` | `optional` | 对应 `amazon_sync_run_log.id` |
| `source_row_hash` | `NVARCHAR(100)` | 是 | - | `required_core` | 原始行 JSON 的 SHA256，用于回刷去重 |
| `raw_data` | `NVARCHAR(MAX)` | 是 | - | `required_core` | 单行原始 JSON；保留未继承前的原始空字段 |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

#### 9.7.2 第一版 `profit_bucket` 草案

| profit_bucket | 含义 | 样例来源 |
|---|---|---|
| `revenue` | 商品销售收入、运费收入等 | Order / ItemPrice / Principal、Shipping |
| `refund` | 退款相关收入冲减 | Refund / ItemPrice |
| `amazon_fee` | 平台佣金、shipping chargeback、月租等 Amazon fee | ItemFees / Commission、Subscription Fee |
| `amazon_fee_refund` | 退款导致的平台佣金返还或调整 | Refund / ItemFees / Commission、RefundCommission |
| `fba_fee` | FBA 配送费、入库配置服务费等 | FBAPerUnitFulfillmentFee、FBA Inbound Placement Service Fee |
| `fba_storage_fee` | 仓储费 | Storage Fee |
| `promotion_cost` | Coupon / promotion 折扣让利 | Promotion / Principal、Shipping |
| `promotion_fee` | Coupon / Deal 平台活动费用 | Coupon Performance Based Fee、Deal Participation Fee |
| `advertising_cost` | 广告扣费的财务入账金额 | Cost of Advertising / TransactionTotalAmount |
| `reimbursement` | FBA 库存赔偿、追回等 | FBA Inventory Reimbursement |
| `liquidation` | 清算收入 | Liquidations / ItemPrice |
| `liquidation_fee` | 清算服务费 | Liquidations / ItemFees |
| `tax_passthrough` | 税收代收代缴相关，不直接视为经营利润 | Tax、MarketplaceFacilitatorTax-*、ItemWithheldTax |
| `reconciliation` | 结算 summary、Payable to Amazon、Successful charge 等对账项 | summary 行 / settlement transfer |
| `unknown` | 尚未分类 | 未来样例补充 |

注意：这是运营分析口径，不是最终会计科目。后续需要用实际月报与会计核对。

#### 9.7.3 第一版财务口径原则

第一版不要直接把 settlement report 汇总成最终利润。应先保留逐行交易明细：

```text
settlement raw rows
    ↓
amazon_settlement_transaction
    ↓
amount_category / profit_bucket 第一版分类
    ↓
人工抽样核对
    ↓
amazon_finance_event 或利润分析中间表
```

费用分类需要基于真实样例逐步确认，特别是：

1. `amount-type` / `amount-description` / `transaction-type` 的组合映射是否覆盖所有费用类型。
2. `Cost of Advertising` 在 settlement 中是财务扣款口径；Ads API 后续用于 campaign / keyword 运营分析口径。
3. 清算、赔偿、订阅费、仓储费、入库配置费等不一定有 SKU，要允许 `seller_sku` 为空。
4. 税收相关字段进入 `tax_passthrough`，第一版利润分析可单独列示，不直接混入经营利润。
5. 金额格式在不同站点可能存在本地化格式，例如小数逗号，因此 parser 需要支持金额格式标准化。

#### 9.7.4 唯一键草案

推荐唯一键先不急着用业务字段硬凑，第一版以 hash 去重为主：

```text
marketplace_id + source_report_type + source_report_id + source_row_hash
```

说明：

1. settlement 明细行不一定都有 `order-id`、`sku` 或 `order-item-code`。
2. 同一结算报告可能存在多行相同订单、不同 amount-description。
3. 用完整原始行 hash 更安全，后续再根据真实样例增加业务索引。

#### 9.7.5 Parser 实现状态

当前 parser 已升级为：

```text
src/seller_data_pipeline/parsers/amazon/settlement_report_parser.py
```

已支持：

1. 解析 Flat File V2 settlement report。
2. 识别 settlement summary 行。
3. 向下继承 summary 行的 settlement period / currency / total amount。
4. 生成 `amount_category` / `profit_bucket` 第一版分类。
5. 保留 `raw_data` 和 `source_row_hash`，暂不写数据库。

聚合分析脚本：

```text
scripts/analyze_settlement_reports.py
```

已生成样例文档：

```text
requirements/data_samples/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.md
```


---


## 10. SKU 成本表设计

`amazon_sku_cost` 可以较早确认，因为它主要来自人工维护，不依赖 Amazon report 字段。

**表状态：`confirmed`**

| 字段 | 类型 | 必填 | 默认值 | 字段状态 | 说明 |
|---|---|---:|---|---|---|
| `id` | `BIGINT IDENTITY(1,1)` | 是 | - | `required_core` | 主键 |
| `marketplace_id` | `NVARCHAR(50)` | 是 | - | `required_core` | Marketplace ID |
| `sku` | `NVARCHAR(200)` | 是 | - | `required_core` | Seller SKU |
| `asin` | `NVARCHAR(50)` | 否 | `NULL` | `optional` | ASIN |
| `product_cost` | `DECIMAL(18,4)` | 是 | `0` | `required_core` | 单件采购成本 |
| `first_mile_cost` | `DECIMAL(18,4)` | 是 | `0` | `required_core` | 单件头程成本 |
| `packaging_cost` | `DECIMAL(18,4)` | 是 | `0` | `required_core` | 单件包装成本 |
| `other_unit_cost` | `DECIMAL(18,4)` | 是 | `0` | `required_core` | 其他单件成本 |
| `currency` | `NVARCHAR(10)` | 是 | - | `required_core` | 成本币种 |
| `effective_from` | `DATE` | 是 | - | `required_core` | 生效开始日 |
| `effective_to` | `DATE` | 否 | `NULL` | `optional` | 生效结束日，空表示仍有效 |
| `remark` | `NVARCHAR(MAX)` | 否 | `NULL` | `optional` | 备注 |
| `created_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 创建时间 |
| `updated_at` | `DATETIME2` | 是 | `SYSUTCDATETIME()` | `required_core` | 更新时间 |

唯一键：

```text
marketplace_id + sku + effective_from
```

---

## 11. Reporting 层草案

以下表当前不建议马上建，因为报表字段依赖 L3 数据稳定后才能确认。

| 表名 | 表状态 | 用途 |
|---|---|---|
| `amazon_weekly_profit_snapshot` | `draft` | 保存周报计算结果，区分快报和稳定盈亏 |
| `amazon_periodic_finance_snapshot` | `draft` | 保存月度/季度财务汇总 |
| `amazon_periodic_report_log` | `draft` | 保存 Excel 文件生成、邮件发送、锁账状态 |

关键原则：

1. 周报/月报/季度包必须保存快照，不能每次实时查询后覆盖历史结论。
2. 报表要记录 `calculation_version`，后续利润计算口径变更时可追溯。
3. 月度/季度会计包是 tax-ready package，不替代会计最终申报。

---

## 12. 数据类型与命名规范

### 12.1 命名

| 类型 | 规则 |
|---|---|
| 表名 | `amazon_` 前缀，snake_case |
| 主键 | `id BIGINT IDENTITY(1,1) PRIMARY KEY` |
| Marketplace 字段 | 统一使用 `marketplace_id`，不再使用模糊的 `marketplace` |
| 时间字段 | 系统时间使用 UTC `DATETIME2` |
| 业务日期 | 使用 `DATE` |
| 金额字段 | `DECIMAL(18,4)` |
| 比例字段 | `DECIMAL(18,6)` |
| JSON 字段 | SQL Server 第一版用 `NVARCHAR(MAX)` |

### 12.2 `updated_at` 维护规则

SQL Server 不会自动更新 `updated_at`。所有 repository 的 update/upsert 必须显式设置：

```sql
updated_at = SYSUTCDATETIME()
```

### 12.3 密钥和敏感信息

数据库不得保存：

```text
LWA client secret
refresh token
access token
Ads API secret
SMTP password
Azure connection secret
```

本地 `.env` 和 Azure Key Vault 才是密钥保存位置。

### 12.4 raw_data 使用规则

`raw_data` 用于保存单行原始数据 JSON，不替代 raw file。

raw file 仍必须保存，因为：

1. parser 变更后可重新解析。
2. 字段映射争议可回溯。
3. 会计/审计需要原始来源证明。

---

## 13. 初始 SQL 生成策略

数据库尚未执行任何 SQL，因此下一阶段不要直接执行当前 `001/002` 草稿。

建议分两种路径：

### 路径 A：先取样，不建表

适合当前马上开发 Reports API 下载闭环。

```text
实现本地 Sampling Mode
下载 raw report
生成本地 manifest
分析 header
更新 database_spec.md
```

优点：

1. 不会过早锁死数据库结构。
2. 可以尽快拿到 Amazon 真实样例。
3. 对 Azure SQL 没有依赖。

缺点：

1. 后续要把 manifest 迁移到数据库。
2. 运行状态不是集中存储。

### 路径 B：先建第一批 Control + Raw 表

适合一开始就希望状态可查询、可追踪。

第一批只建：

```text
amazon_marketplace
amazon_sync_run_log
amazon_report_request
amazon_raw_report_file
amazon_report_field_catalog
amazon_sku_cost
```

暂不建：

```text
amazon_sales_traffic_daily
amazon_inventory_daily
amazon_finance_event
amazon_ads_daily
amazon_promotion_daily
amazon_weekly_profit_snapshot
amazon_periodic_finance_snapshot
amazon_periodic_report_log
```

推荐判断：

```text
如果你想最快拿样例：先走路径 A。
如果你想尽早验证 Azure SQL 写入：走路径 B。
```

当前建议：**先走路径 A，但代码接口按路径 B 的表字段设计，方便后续切换到数据库。**

---

## 14. 下一阶段接口取样顺序

建议按风险从低到高取样。

| 顺序 | 数据 | 候选 report/API | 目的 |
|---:|---|---|---|
| 1 | Listing / Open Listings | `GET_MERCHANT_LISTINGS_ALL_DATA` 或 `GET_FLAT_FILE_OPEN_LISTINGS_DATA` | 字段简单，验证 Reports API 全链路 |
| 2 | 库存 | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | 已完成首份样例；继续确认库存口径 |
| 3 | 销售和流量 | `GET_SALES_AND_TRAFFIC_REPORT` | 已完成 7 天窗口样例；日期维度与 PARENT ASIN 维度进入 sampling |
| 4 | 财务 | Finances API / settlement report | 确认费用、退款、赔偿、清算分类 |
| 5 | 广告 | Amazon Ads Reporting | 确认 Sponsored Products 粒度与归因字段 |
| 6 | 促销 | 财务事件 + Seller Central 导出/可用 API | 确认 Coupon / Deal / Price Discount 成本来源 |

第一份真实报告建议使用 Listing 类报告，原因：

1. 不涉及复杂金额归类。
2. 通常是 tab-delimited flat file。
3. 能验证 report request、document 下载、解压、编码、header 解析。
4. 能拿到 SKU / ASIN 基础数据，后续所有表都需要。

---

## 15. 字段来源追踪模板

每当拿到一个新 report 样例，必须在本文档或配套字段映射文件中记录：

| 项目 | 示例 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_MERCHANT_LISTINGS_ALL_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| requested_at | 运行时记录 |
| raw_file_path | `data/raw/...` |
| sha256 | 文件校验值 |
| encoding | 解析推断值 |
| delimiter | `tab` |
| header_fields | 原始字段列表 |
| row_count | 数据行数 |
| sample_rows | 脱敏后的前几行样例 |
| target_table_candidates | 建议进入哪些表 |
| unresolved_questions | 未确定问题 |

---

## 16. 第一阶段验收标准

下一阶段完成后，不要求数据库已建完所有业务表，但应该完成：

1. `requirements/database_spec.md` 已更新为 v0.2 或更高版本。
2. 当前 SQL 草稿明确不直接执行，后续必须按 spec 重写。
3. Reports API client 能提交 Listing、FBA inventory、Sales and Traffic report request。
4. 本地 Sampling Mode 能记录 request manifest。
5. collect 脚本能轮询 `reportId`。
6. 报告 `DONE` 后能下载 raw file。
7. raw file 能保存到 `data/raw/`。
8. 能生成 raw file manifest，包含 path、sha256、row_count、column_count、encoding。
9. 能读取 header，并产出字段样例清单。
10. 根据样例更新本文档中的 L3 业务表字段。
11. 已为 Listing、FBA 库存、销售与流量报告新增 parser 草案。

---

## 17. 后续待确认问题

以下问题不阻塞下一阶段取样：

1. 销售日表第一版已选择 `GET_SALES_AND_TRAFFIC_REPORT`，但还需补充多日和非零销售样例。
2. 库存表第一版已决定以 FBA 可履约库存 `afn-fulfillable-quantity` 为主，但仍需更多日期样例验证。
3. 财务数据优先用 Finances API 还是 settlement report。
4. Coupon / Deal / Price Discount 是否有稳定 API；如果没有，是否从财务事件中归类。
5. Ads API 授权和 profile id 获取流程。
6. 周报业务日期按 Amazon US 站点日期还是 Europe/London 运行日期。
7. 月度/季度包是否需要自动换算 GBP；第一版建议只保留 USD，汇率交由会计或后续模块处理。

---

## 18. 当前结论

当前不要直接执行 SQL 建表。

下一步最合理的开发任务是：

```text
1. 在代码中增加本地 Sampling Mode 的目录和 manifest 设计。
2. 实现 SP-API Reports API 的 createReport/getReport/getReportDocument/download。
3. 用 Listing 报告跑通第一个 raw file 下载闭环。
4. 解析 header 和前几行样例。
5. 回到本文件更新 L3 normalized 表字段。
6. 继续取样更长日期窗口的销售/流量和财务数据。
7. 等第一批字段稳定后，再重写 001/002 SQL。
```

这条路线能避免过早设计错误，同时不会阻塞真实接口开发。


## 19. v0.9 批量接口取样计划

当前进入“尽量下载可用样例”的阶段，但仍不建表。

新增取样计划文档：

```text
requirements/amazon_report_sampling_plan.md
```

新增批量脚本：

```text
scripts/run_sampling_plan.py
```

默认非敏感计划覆盖：

| 数据域 | report/API | 目标用途 |
|---|---|---|
| Listing | `GET_MERCHANT_LISTINGS_ALL_DATA` | SKU / ASIN / listing / price / status |
| FBA 库存 | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | 可售、预留、入库、不可售库存 |
| 销售与流量 | `GET_SALES_AND_TRAFFIC_REPORT` | 日期/ASIN 粒度销售、流量、转化 |
| 订单明细 | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | 订单、SKU、ASIN、订单状态、促销折扣 |
| 退货 | `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` | 退货原因、RMA、状态 |
| FBA 赔偿 | `GET_FBA_REIMBURSEMENTS_DATA` | 赔偿原因、金额、数量 |
| FBA 费用预估 | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | referral fee / FBA fee 预估 |
| FBA 仓储费 | `GET_FBA_STORAGE_FEE_CHARGES_DATA` | 月度仓储费和库存体积 |
| 库存健康 | `GET_FBA_INVENTORY_PLANNING_DATA` | 库龄、周转、冗余、建议动作 |
| 库存流水 | `GET_LEDGER_SUMMARY_VIEW_DATA` / `GET_LEDGER_DETAIL_VIEW_DATA` | 收货、发货、退货、丢失、损坏、调整 |
| Settlement | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | 实际结算明细与费用分类 |
| 促销/Coupon | `GET_PROMOTION_PERFORMANCE_REPORT` / `GET_COUPON_PERFORMANCE_REPORT` | 若账号可用，辅助活动效果分析 |

敏感报告默认不跑：

| report/API | 原因 |
|---|---|
| `GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL` | 可能包含买家联系方式/地址相关字段 |
| `GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA` | 可能包含 customer-comments |

后续处理规则：

1. 批量脚本只负责提交/发现 report，不负责建库。
2. `collect_ready_reports.py --limit 50` 下载 raw file。
3. 每个新 report 下载后，先用 analyzer 生成脱敏字段样例。
4. 根据样例更新本 spec。
5. parser 与 normalized 表设计确认后，再统一重写 SQL。

## 20. v1.0 批量取样结果与新增 normalized 草案

本轮批量取样已经下载并分析以下新增 raw report：

| 数据域 | report_type | 样例结果 | 建议目标表 | 设计状态 |
|---|---|---:|---|---|
| 订单明细 | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | 112 行 / 33 字段 | `amazon_order_item` | `sampling` |
| 退货请求 | `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` | 0 行 / 33 字段，header-only | `amazon_return_request` | `sampling` |
| FBA 赔偿 | `GET_FBA_REIMBURSEMENTS_DATA` | 19 行 / 18 字段 | `amazon_fba_reimbursement` | `sampling` |
| FBA 费用预估 | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | 8 行 / 31 字段 | `amazon_fba_fee_preview` | `sampling` |
| 库存健康 | `GET_FBA_INVENTORY_PLANNING_DATA` | 4 行 / 97 字段 | `amazon_inventory_planning_daily` | `sampling` |
| 库存流水汇总 | `GET_LEDGER_SUMMARY_VIEW_DATA` | 150 行 / 22 字段 | `amazon_inventory_ledger_summary_daily` | `sampling` |

本轮还观察到：

1. `GET_FBA_STORAGE_FEE_CHARGES_DATA` 已成功提交但最终 `CANCELLED`，当前窗口可能无可生成数据，暂不建表。
2. `GET_PROMOTION_PERFORMANCE_REPORT` 在首次轮询时仍为 `IN_PROGRESS`，应继续运行 `collect_ready_reports.py --limit 50`。
3. `GET_COUPON_PERFORMANCE_REPORT` 返回 `FATAL`，且 Amazon 给出了 `reportDocumentId`；后续可考虑增强 collect 脚本，下载 FATAL document 用于诊断。
4. `GET_LEDGER_DETAIL_VIEW_DATA` 使用 `reportOptions={"eventType":""}` 被当前 SP-API 校验拒绝；后续批量计划改为不显式传空字符串，先尝试无 `reportOptions`。

### 20.1 `amazon_order_item`

**表状态：`sampling`**  
**第一数据来源：** `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL`  
**样例记录：** `requirements/data_samples/GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL.md`

用途：保存订单行项目维度数据，用于按 SKU/ASIN/订单状态/履约渠道/促销折扣分析销售。

第一版建议字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `marketplace_id` | `NVARCHAR(50)` | `required_core` | Marketplace ID |
| `amazon_order_id` | `NVARCHAR(100)` | `observed` | `amazon-order-id` |
| `merchant_order_id` | `NVARCHAR(100)` | `observed` | `merchant-order-id` |
| `purchase_date_raw` | `NVARCHAR(100)` | `observed` | `purchase-date` |
| `last_updated_date_raw` | `NVARCHAR(100)` | `observed` | `last-updated-date` |
| `order_status` | `NVARCHAR(80)` | `observed` | `order-status` |
| `fulfillment_channel` | `NVARCHAR(80)` | `observed` | `fulfillment-channel` |
| `sales_channel` | `NVARCHAR(100)` | `observed` | `sales-channel` |
| `product_name` | `NVARCHAR(1000)` | `observed` | `product-name` |
| `seller_sku` | `NVARCHAR(200)` | `observed` | `sku` |
| `asin` | `NVARCHAR(50)` | `observed` | `asin` |
| `item_status` | `NVARCHAR(80)` | `observed` | `item-status` |
| `quantity` | `INT` | `observed` | `quantity` |
| `currency` | `NVARCHAR(10)` | `observed` | `currency` |
| `item_price` | `DECIMAL(18,4)` | `observed` | `item-price` |
| `item_tax` | `DECIMAL(18,4)` | `observed` | `item-tax` |
| `shipping_price` | `DECIMAL(18,4)` | `observed` | `shipping-price` |
| `shipping_tax` | `DECIMAL(18,4)` | `observed` | `shipping-tax` |
| `item_promotion_discount` | `DECIMAL(18,4)` | `observed` | `item-promotion-discount` |
| `ship_promotion_discount` | `DECIMAL(18,4)` | `observed` | `ship-promotion-discount` |
| `ship_state` | `NVARCHAR(100)` | `optional` | `ship-state`，低敏地理维度 |
| `ship_postal_code` | `NVARCHAR(50)` | `optional` | `ship-postal-code`，后续可考虑脱敏/截断 |
| `ship_country` | `NVARCHAR(20)` | `observed` | `ship-country` |
| `promotion_ids` | `NVARCHAR(MAX)` | `optional` | `promotion-ids` |
| `is_business_order` | `BIT` | `observed` | `is-business-order` |

注意：订单报告可用于运营销售行项目分析，但利润最终仍应以 settlement/finance 费用口径做对账。

### 20.2 `amazon_return_request`

**表状态：`sampling`**  
**第一数据来源：** `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE`  
**样例记录：** `requirements/data_samples/GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE.md`

用途：保存退货请求、RMA、退货原因、Safe-T、退款金额等。

本次样例是 header-only，说明窗口内无返回行；字段结构已可进入 parser 草案，但还需要未来补充含数据行样例。

第一版建议字段：`order_id`、`order_date_raw`、`return_request_date_raw`、`return_request_status`、`amazon_rma_id`、`merchant_rma_id`、`currency_code`、`asin`、`seller_sku`、`item_name`、`return_quantity`、`return_reason`、`return_type`、`resolution`、`refunded_amount`、`order_item_id`、`safe_t_claim_id`、`safe_t_claim_state`。

### 20.3 `amazon_fba_reimbursement`

**表状态：`sampling`**  
**第一数据来源：** `GET_FBA_REIMBURSEMENTS_DATA`  
**样例记录：** `requirements/data_samples/GET_FBA_REIMBURSEMENTS_DATA.md`

用途：保存 FBA 赔偿明细，用于识别赔现金、赔库存、CustomerReturn 相关赔偿和原始 reimbursement id。

第一版建议字段：`approval_date_raw`、`reimbursement_id`、`case_id`、`amazon_order_id`、`reason`、`seller_sku`、`fnsku`、`asin`、`product_name`、`condition`、`currency`、`amount_per_unit`、`amount_total`、`quantity_reimbursed_cash`、`quantity_reimbursed_inventory`、`quantity_reimbursed_total`、`original_reimbursement_id`、`original_reimbursement_type`。

### 20.4 `amazon_fba_fee_preview`

**表状态：`sampling`**  
**第一数据来源：** `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA`  
**样例记录：** `requirements/data_samples/GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA.md`

用途：保存 SKU/FNSKU/ASIN 维度 FBA 费用预估，用于新品定价、利润预估和与真实 settlement fee 做差异分析。

第一版建议字段：`seller_sku`、`fnsku`、`asin`、`amazon_store`、`product_name`、`product_group`、`brand`、`fulfilled_by`、`your_price`、`sales_price`、`currency`、`estimated_fee_total`、`estimated_referral_fee_per_unit`、`estimated_variable_closing_fee`、`expected_fulfillment_fee_per_unit`、`estimated_future_fee_total`、`product_size_tier`、包裹尺寸和重量字段。

注意：样例中 `amazon-store` 出现 US/CA 等值，后续唯一键应包含 `amazon_store` 或映射后的 marketplace。

### 20.5 `amazon_inventory_planning_daily`

**表状态：`sampling`**  
**第一数据来源：** `GET_FBA_INVENTORY_PLANNING_DATA`  
**样例记录：** `requirements/data_samples/GET_FBA_INVENTORY_PLANNING_DATA.md`

用途：保存库存健康、库龄、周转、冗余和 Amazon 建议动作。

第一版正式列优先保留：`snapshot_date_raw`、`seller_sku`、`fnsku`、`asin`、`available_quantity`、`pending_removal_quantity`、各库龄段、`units_shipped_t7/t30/t60/t90`、`alert`、`recommended_action`、`sell_through`、`days_of_supply`、`estimated_excess_quantity`、`recommended_removal_quantity`。

由于本报告字段多达 97 个，低频或空值字段先保留在 `raw_data`，不要一次性全部建成正式列。

### 20.6 `amazon_inventory_ledger_summary_daily`

**表状态：`sampling`**  
**第一数据来源：** `GET_LEDGER_SUMMARY_VIEW_DATA`，当前样例使用 `aggregateByLocation=COUNTRY`、`aggregatedByTimePeriod=DAILY`。  
**样例记录：** `requirements/data_samples/GET_LEDGER_SUMMARY_VIEW_DATA.md`

用途：保存 FBA 库存流水汇总，用于解释库存变化和差异：收货、客户发货、客户退货、仓库调拨、找到、丢失、损坏、销毁、其他事件。

第一版建议字段：`ledger_date_raw`、`fnsku`、`asin`、`seller_sku`、`title`、`disposition`、`starting_warehouse_balance`、`in_transit_between_warehouses`、`receipts`、`customer_shipments`、`customer_returns`、`vendor_returns`、`warehouse_transfer_in_out`、`found`、`lost`、`damaged`、`disposed`、`other_events`、`ending_warehouse_balance`、`unknown_events`、`location`、`store`。

后续如需要仓库维度，可追加取样 `aggregateByLocation=FC`。


---

## 21. v1.1 第二轮批量取样结果、诊断下载与新增库存表草案

本轮继续执行扩展后的批量取样计划，新增下载并分析：

| 数据域 | report_type | 样例结果 | 建议目标表 | 设计状态 |
|---|---|---:|---|---|
| 库存流水明细 | `GET_LEDGER_DETAIL_VIEW_DATA` | 207 行 / 16 字段 | `amazon_inventory_ledger_detail` | `sampling` |
| 预留库存 | `GET_RESERVED_INVENTORY_DATA` | 5 行 / 9 字段 | `amazon_reserved_inventory_daily` | `sampling` |
| 补货建议 | `GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT` | 5 行 / 30 字段 | `amazon_restock_inventory_recommendation` | `sampling` |

本轮还观察到：

1. `GET_FBA_STORAGE_FEE_CHARGES_DATA`、`GET_STRANDED_INVENTORY_UI_DATA`、`GET_FBA_RECOMMENDED_REMOVAL_DATA`、`GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA`、`GET_FBA_OVERAGE_FEE_CHARGES_DATA` 返回 `CANCELLED`，且没有 `reportDocumentId`。当前阶段解释为：该账号/该期间没有可生成数据、报告不适用或该报告在当前站点/条件下不可用；暂不阻塞建模。
2. `GET_COUPON_PERFORMANCE_REPORT` 返回 `FATAL`，但带有 `reportDocumentId`。后续 collect 会下载 diagnostic document，作为诊断文件保存，不作为业务 raw data。
3. `GET_PROMOTION_PERFORMANCE_REPORT` 长时间 `IN_PROGRESS`。短期不阻塞：促销/Coupon 成本仍可先通过 settlement 的 `promotion-id`、`amount-type`、`amount-description` 分类做财务口径分析。
4. Discovery 类报告必须避免覆盖已下载 manifest，否则会导致已下载 settlement 报告重复进入待下载队列。后续逻辑已调整为保留 `download_status=DOWNLOADED` 的本地状态。

### 21.1 `amazon_inventory_ledger_detail`

**表状态：`sampling`**  
**第一数据来源：** `GET_LEDGER_DETAIL_VIEW_DATA`  
**样例记录：** `requirements/data_samples/GET_LEDGER_DETAIL_VIEW_DATA.md`

用途：保存 FBA 库存流水明细事件，解释库存每日变化来源，例如 Shipments、CustomerReturns、WhseTransfers 等。

第一版建议字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `marketplace_id` | `NVARCHAR(50)` | `required_core` | Marketplace ID |
| `ledger_date_raw` | `NVARCHAR(50)` | `observed` | `Date` |
| `fnsku` | `NVARCHAR(100)` | `observed` | `FNSKU` |
| `asin` | `NVARCHAR(50)` | `observed` | `ASIN` |
| `seller_sku` | `NVARCHAR(200)` | `observed` | `MSKU` |
| `title` | `NVARCHAR(1000)` | `observed` | `Title` |
| `event_type` | `NVARCHAR(100)` | `observed` | `Event Type` |
| `reference_id` | `NVARCHAR(200)` | `optional` | `Reference ID`，样例多为空 |
| `quantity` | `INT` | `observed` | `Quantity`，可正可负 |
| `fulfillment_center` | `NVARCHAR(50)` | `observed` | `Fulfillment Center` |
| `disposition` | `NVARCHAR(80)` | `observed` | `Disposition` |
| `reason` | `NVARCHAR(200)` | `optional` | `Reason` |
| `country` | `NVARCHAR(20)` | `observed` | `Country` |
| `reconciled_quantity` | `INT` | `observed` | `Reconciled Quantity` |
| `unreconciled_quantity` | `INT` | `observed` | `Unreconciled Quantity` |
| `date_time_raw` | `NVARCHAR(100)` | `observed` | `Date and Time` |
| `store` | `NVARCHAR(100)` | `optional` | `Store` |
| `source_report_id` / `source_raw_file_path` / `source_row_hash` / `raw_data` | 通用溯源字段 | `required_core` | 所有 normalized 表保留 |

建议唯一键草案：`marketplace_id + source_report_id + source_row_hash`。后续如确认 `Date and Time + FNSKU + Event Type + Fulfillment Center + Quantity` 足够稳定，可再设计业务唯一键。

### 21.2 `amazon_reserved_inventory_daily`

**表状态：`sampling`**  
**第一数据来源：** `GET_RESERVED_INVENTORY_DATA`  
**样例记录：** `requirements/data_samples/GET_RESERVED_INVENTORY_DATA.md`

用途：保存 FBA reserved inventory 拆分，解释 `afn-reserved-quantity` 的构成。

第一版建议字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `marketplace_id` | `NVARCHAR(50)` | `required_core` | Marketplace ID |
| `snapshot_date` | `DATE` | `derived` | 下载日期或运行日期；原 report 无明确 snapshot date |
| `seller_sku` | `NVARCHAR(200)` | `observed` | `sku` |
| `fnsku` | `NVARCHAR(100)` | `observed` | `fnsku` |
| `asin` | `NVARCHAR(50)` | `observed` | `asin` |
| `product_name` | `NVARCHAR(1000)` | `observed` | `product-name` |
| `reserved_quantity` | `INT` | `observed` | `reserved_qty` |
| `reserved_customer_orders` | `INT` | `observed` | `reserved_customerorders` |
| `reserved_fc_transfers` | `INT` | `observed` | `reserved_fc-transfers` |
| `reserved_fc_processing` | `INT` | `observed` | `reserved_fc-processing` |
| `program` | `NVARCHAR(100)` | `optional` | `program`，样例为空 |
| `source_report_id` / `source_raw_file_path` / `source_row_hash` / `raw_data` | 通用溯源字段 | `required_core` | 所有 normalized 表保留 |

建议唯一键草案：`marketplace_id + snapshot_date + seller_sku + fnsku`。

### 21.3 `amazon_restock_inventory_recommendation`

**表状态：`sampling`**  
**第一数据来源：** `GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT`  
**样例记录：** `requirements/data_samples/GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT.md`

用途：保存 Amazon 补货建议、库存覆盖天数、30 天销量、推荐补货量和建议发货日期，用于清仓/补货/库存健康分析。

第一版建议字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `marketplace_id` | `NVARCHAR(50)` | `required_core` | Marketplace ID |
| `snapshot_date` | `DATE` | `derived` | 下载日期或运行日期；原 report 无明确 snapshot date |
| `country` | `NVARCHAR(20)` | `observed` | `Country` |
| `product_name` | `NVARCHAR(1000)` | `observed` | `Product Name` |
| `fnsku` | `NVARCHAR(100)` | `observed` | `FNSKU` |
| `seller_sku` | `NVARCHAR(200)` | `observed` | `Merchant SKU` |
| `asin` | `NVARCHAR(50)` | `observed` | `ASIN` |
| `condition` | `NVARCHAR(80)` | `observed` | `Condition` |
| `supplier` | `NVARCHAR(200)` | `optional` | `Supplier` |
| `currency_code` | `NVARCHAR(10)` | `observed` | `Currency code` |
| `price` | `DECIMAL(18,4)` | `observed` | `Price` |
| `sales_last_30_days` | `DECIMAL(18,4)` | `observed` | `Sales last 30 days` |
| `units_sold_last_30_days` | `INT` | `observed` | `Units Sold Last 30 Days` |
| `total_units` | `INT` | `observed` | `Total Units` |
| `inbound_quantity` | `INT` | `observed` | `Inbound` |
| `available_quantity` | `INT` | `observed` | `Available` |
| `fc_transfer_quantity` | `INT` | `observed` | `FC transfer` |
| `fc_processing_quantity` | `INT` | `observed` | `FC Processing` |
| `customer_order_quantity` | `INT` | `observed` | `Customer Order` |
| `unfulfillable_quantity` | `INT` | `observed` | `Unfulfillable` |
| `working_quantity` / `shipped_quantity` / `receiving_quantity` | `INT` | `observed` | 入库阶段拆分 |
| `fulfilled_by` | `NVARCHAR(100)` | `observed` | `Fulfilled by` |
| `total_days_of_supply` | `INT` | `observed` | `Total Days of Supply...` |
| `days_of_supply_at_amazon_fulfillment_network` | `INT` | `observed` | `Days of Supply at Amazon Fulfillment Network` |
| `alert` | `NVARCHAR(500)` | `optional` | `Alert` |
| `recommended_replenishment_quantity` | `INT` | `observed` | `Recommended replenishment qty` |
| `recommended_ship_date_raw` | `NVARCHAR(100)` | `optional` | `Recommended ship date` |
| `recommended_action` | `NVARCHAR(500)` | `optional` | `Recommended action` |
| `unit_storage_size` | `DECIMAL(18,6)` | `observed` | `Unit storage size` |
| `source_report_id` / `source_raw_file_path` / `source_row_hash` / `raw_data` | 通用溯源字段 | `required_core` | 所有 normalized 表保留 |

建议唯一键草案：`marketplace_id + snapshot_date + seller_sku + fnsku`。

---

## 22. 当前下载失败/取消报告的处理原则

| report_type | 当前状态 | 是否阻塞建库 | 处理方式 |
|---|---|---:|---|
| `GET_FBA_STORAGE_FEE_CHARGES_DATA` | `CANCELLED` | 否 | 先通过 settlement 识别 storage fee；后续到月末/出账后重试 |
| `GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA` | `CANCELLED` | 否 | 同上，当前无长期仓储费数据也合理 |
| `GET_FBA_OVERAGE_FEE_CHARGES_DATA` | `CANCELLED` | 否 | 同上，当前无超量仓储费数据也合理 |
| `GET_STRANDED_INVENTORY_UI_DATA` | `CANCELLED` | 否 | 当前无 stranded 库存样例；暂不建正式表 |
| `GET_FBA_RECOMMENDED_REMOVAL_DATA` | `CANCELLED` | 否 | 当前无移除建议样例；暂不建正式表 |
| `GET_COUPON_PERFORMANCE_REPORT` | `DONE` | 否 | 带 couponStartDateFrom / couponStartDateTo 后已成功下载；作为 Coupon 运营效果补充口径 |
| `GET_PROMOTION_PERFORMANCE_REPORT` | `DONE` | 否 | 带 promotionStartDateFrom / promotionStartDateTo 后已成功下载；作为 Promotion/Deal 运营效果补充口径 |

原则：仓储费、滞留、移除等取消类报告不影响当前主数据库设计。利润核算所需的费用侧数据，优先以 settlement 作为财务事实来源；Promotion/Coupon Performance report 已完成运营效果取样，但不直接替代 settlement 财务费用口径。

---

## 23. v1.3 Promotion / Coupon Performance 成功取样与表草案

本轮复测确认，`GET_PROMOTION_PERFORMANCE_REPORT` 与 `GET_COUPON_PERFORMANCE_REPORT` 在传入专用日期 `reportOptions` 后可以正常生成并下载业务报告。

| 数据域 | report_type | 样例结果 | 建议目标表 | 设计状态 |
|---|---|---:|---|---|
| Promotion / Deal 运营效果 | `GET_PROMOTION_PERFORMANCE_REPORT` | 1 个 promotion / 3 个 includedProducts | `amazon_promotion_performance`、`amazon_promotion_product_performance` | `sampling` |
| Coupon 运营效果 | `GET_COUPON_PERFORMANCE_REPORT` | 2 个 coupons / 4 个 coupon ASIN 关系 | `amazon_coupon_performance`、`amazon_coupon_asin` | `sampling` |

重要口径：

1. Promotion / Coupon Performance report 是**运营效果口径**，适合评估活动曝光、销量、领取、兑换、预算消耗、销售额等。
2. 第一版利润核算仍以 Settlement V2 作为**财务事实口径**，Promotion / Coupon report 不直接替代 settlement 中的实际费用、折扣和扣款。
3. Promotion report 的 `includedProducts` 是嵌套数组，应拆为活动主表与活动商品表。Coupon report 的 `asins` 是嵌套数组，应拆为 Coupon 主表与 Coupon-ASIN 关系表。

### 23.1 `amazon_promotion_performance`

**表状态：`sampling`**  
**第一数据来源：** `GET_PROMOTION_PERFORMANCE_REPORT`  
**样例记录：** `requirements/data_samples/GET_PROMOTION_PERFORMANCE_REPORT.md`

用途：保存 Promotion / Deal 活动主表，用于分析活动整体曝光、销售件数和销售额。

第一版建议字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `marketplace_id` | `NVARCHAR(50)` | `required_core` | `marketplaceId` |
| `promotion_id` | `NVARCHAR(100)` | `observed` | `promotionId` |
| `merchant_id` | `NVARCHAR(100)` | `observed` | `merchantId` |
| `promotion_name` | `NVARCHAR(500)` | `observed` | `promotionName` |
| `promotion_type` | `NVARCHAR(100)` | `observed` | `type`，如 `BEST_DEAL` |
| `status` | `NVARCHAR(100)` | `observed` | `status` |
| `glance_views` | `INT` | `observed` | `glanceViews` |
| `units_sold` | `INT` | `observed` | `unitsSold` |
| `revenue` | `DECIMAL(18,4)` | `observed` | `revenue` |
| `revenue_currency_code` | `NVARCHAR(10)` | `observed` | `revenueCurrencyCode` |
| `start_date_time_raw` / `end_date_time_raw` | `NVARCHAR(100)` | `observed` | `startDateTime` / `endDateTime` |
| `created_date_time_raw` / `last_updated_date_time_raw` | `NVARCHAR(100)` | `observed` | `createdDateTime` / `lastUpdatedDateTime` |
| `source_report_id` / `source_raw_file_path` / `source_row_hash` / `raw_data` | 通用溯源字段 | `required_core` | 所有 normalized 表保留 |

建议唯一键草案：`marketplace_id + promotion_id + source_report_id`。后续如需保留同一 promotion 多次快照，可改为 `marketplace_id + promotion_id + snapshot_date`。

### 23.2 `amazon_promotion_product_performance`

**表状态：`sampling`**  
**第一数据来源：** `GET_PROMOTION_PERFORMANCE_REPORT.promotions[].includedProducts[]`

用途：保存 Promotion / Deal 关联商品维度表现。

第一版建议字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `marketplace_id` | `NVARCHAR(50)` | `required_core` | 父级 `marketplaceId` |
| `promotion_id` | `NVARCHAR(100)` | `observed` | 父级 `promotionId` |
| `promotion_name` / `promotion_type` / `status` | `NVARCHAR` | `observed` | 父级活动字段冗余，方便分析 |
| `asin` | `NVARCHAR(50)` | `observed` | `includedProducts[].asin` |
| `product_name` | `NVARCHAR(1000)` | `observed` | `includedProducts[].productName` |
| `product_glance_views` | `INT` | `observed` | `productGlanceViews` |
| `product_units_sold` | `INT` | `observed` | `productUnitsSold` |
| `product_revenue` | `DECIMAL(18,4)` | `observed` | `productRevenue` |
| `product_revenue_currency_code` | `NVARCHAR(10)` | `observed` | `productRevenueCurrencyCode` |
| `source_report_id` / `source_raw_file_path` / `source_row_hash` / `raw_data` | 通用溯源字段 | `required_core` | 所有 normalized 表保留 |

建议唯一键草案：`marketplace_id + promotion_id + asin + source_report_id`。

### 23.3 `amazon_coupon_performance`

**表状态：`sampling`**  
**第一数据来源：** `GET_COUPON_PERFORMANCE_REPORT`  
**样例记录：** `requirements/data_samples/GET_COUPON_PERFORMANCE_REPORT.md`

用途：保存 Coupon 主表，用于分析预算、预算消耗、领取、兑换、折扣、销售额等。

第一版建议字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `marketplace_id` | `NVARCHAR(50)` | `required_core` | `marketplaceId` |
| `coupon_id` | `NVARCHAR(100)` | `observed` | `couponId` |
| `merchant_id` | `NVARCHAR(100)` | `observed` | `merchantId` |
| `currency_code` | `NVARCHAR(10)` | `observed` | `currencyCode` |
| `name` / `website_message` | `NVARCHAR(500)` | `observed` | `name` / `websiteMessage` |
| `start_date_time_raw` / `end_date_time_raw` | `NVARCHAR(100)` | `observed` | `startDateTime` / `endDateTime` |
| `discount_type` | `NVARCHAR(100)` | `observed` | `discountType` |
| `discount_amount` | `DECIMAL(18,4)` | `observed` | `discountAmount` |
| `total_discount` | `DECIMAL(18,4)` | `observed` | `totalDiscount` |
| `clips` / `redemptions` | `INT` | `observed` | `clips` / `redemptions` |
| `budget` / `budget_spent` / `budget_remaining` | `DECIMAL(18,4)` | `observed` | 预算与已消耗预算 |
| `budget_percentage_used` | `DECIMAL(9,4)` | `observed` | `budgetPercentageUsed` |
| `sales` | `DECIMAL(18,4)` | `observed` | `sales` |
| `source_report_id` / `source_raw_file_path` / `source_row_hash` / `raw_data` | 通用溯源字段 | `required_core` | 所有 normalized 表保留 |

建议唯一键草案：`marketplace_id + coupon_id + source_report_id`。后续如需保留同一 coupon 多次快照，可改为 `marketplace_id + coupon_id + snapshot_date`。

### 23.4 `amazon_coupon_asin`

**表状态：`sampling`**  
**第一数据来源：** `GET_COUPON_PERFORMANCE_REPORT.coupons[].asins[]`

用途：保存 Coupon 与 ASIN 的关联关系。

第一版建议字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `marketplace_id` | `NVARCHAR(50)` | `required_core` | 父级 `marketplaceId` |
| `coupon_id` | `NVARCHAR(100)` | `observed` | 父级 `couponId` |
| `merchant_id` | `NVARCHAR(100)` | `observed` | 父级 `merchantId` |
| `asin` | `NVARCHAR(50)` | `observed` | `asins[].asin` |
| `coupon_name` | `NVARCHAR(500)` | `observed` | 父级 `name`，方便分析 |
| `currency_code` | `NVARCHAR(10)` | `observed` | 父级 `currencyCode` |
| `start_date_time_raw` / `end_date_time_raw` | `NVARCHAR(100)` | `observed` | 父级活动时间 |
| `source_report_id` / `source_raw_file_path` / `source_row_hash` / `raw_data` | 通用溯源字段 | `required_core` | 所有 normalized 表保留 |

建议唯一键草案：`marketplace_id + coupon_id + asin + source_report_id`。



## 24. Amazon Ads API normalized 表草案

> 当前状态：`draft`。以下字段基于 Ads Reporting v3 取样计划，不是最终建表字段。必须等真实 Ads raw report 下载后，再用字段样例更新为 `sampling`。

### 24.1 `amazon_ads_profile`

**表状态：`draft`**  
**第一数据来源：** Amazon Ads `/v2/profiles`

用途：保存 Ads profile 与 marketplace / advertiser account 的映射。

第一版候选字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `profile_id` | `NVARCHAR(100)` | `candidate` | `profileId` |
| `country_code` | `NVARCHAR(10)` | `candidate` | `countryCode` |
| `currency_code` | `NVARCHAR(10)` | `candidate` | `currencyCode` |
| `timezone` | `NVARCHAR(100)` | `candidate` | `timezone` |
| `account_id` | `NVARCHAR(100)` | `candidate` | `accountInfo.id` |
| `account_name` | `NVARCHAR(500)` | `candidate` | `accountInfo.name` |
| `account_type` | `NVARCHAR(100)` | `candidate` | `accountInfo.type` |
| `raw_data` | `NVARCHAR(MAX)` | `required_core` | 原始 profile JSON |

### 24.2 `amazon_ads_sp_campaign_daily`

**表状态：`draft`**  
**第一数据来源：** Ads Reporting v3 `reportTypeId=spCampaigns`

用途：保存 Sponsored Products campaign 维度广告表现。

候选字段：

| 字段 | 类型 | 字段状态 | 来源字段 / 说明 |
|---|---|---|---|
| `profile_id` | `NVARCHAR(100)` | `candidate` | request scope profile |
| `report_date` | `DATE` | `candidate` | `date` |
| `campaign_id` | `NVARCHAR(100)` | `candidate` | `campaignId` |
| `campaign_name` | `NVARCHAR(500)` | `candidate` | `campaignName` |
| `campaign_status` | `NVARCHAR(100)` | `candidate` | `campaignStatus` |
| `impressions` / `clicks` | `INT` | `candidate` | 曝光与点击 |
| `cost` | `DECIMAL(18,4)` | `candidate` | 广告花费；币种需结合 profile 或返回字段确认 |
| `sales_7d` | `DECIMAL(18,4)` | `candidate` | `sales7d` |
| `purchases_7d` | `INT` | `candidate` | `purchases7d` |
| `units_sold_clicks_7d` | `INT` | `candidate` | `unitsSoldClicks7d` |
| `source_ads_report_id` / `source_raw_file_path` / `source_row_hash` / `raw_data` | 通用溯源字段 | `required_core` | Ads normalized 表保留 |

### 24.3 `amazon_ads_sp_targeting_daily`

**表状态：`draft`**  
**第一数据来源：** Ads Reporting v3 `reportTypeId=spTargeting`

用途：保存 keyword / targeting 维度表现，用于调价、否词、关键词筛选。候选字段包括：`profile_id`、`report_date`、`campaign_id`、`campaign_name`、`ad_group_id`、`ad_group_name`、`keyword_id`、`keyword`、`match_type`、`targeting`、`impressions`、`clicks`、`cost`、`sales_7d`、`purchases_7d`、`units_sold_clicks_7d` 以及通用溯源字段。

### 24.4 `amazon_ads_sp_search_term_daily`

**表状态：`draft`**  
**第一数据来源：** Ads Reporting v3 `reportTypeId=spSearchTerm`

用途：保存用户搜索词表现，用于找词、加词、否词。候选字段包括 `search_term`，以及 campaign / ad group / keyword / targeting / impressions / clicks / cost / sales / purchases 等字段。

### 24.5 `amazon_ads_sp_advertised_product_daily`

**表状态：`draft`**  
**第一数据来源：** Ads Reporting v3 `reportTypeId=spAdvertisedProduct`

用途：保存广告推广 SKU / ASIN 维度表现，用于判断哪个产品广告效率高。候选字段包括：`advertised_asin`、`advertised_sku`、campaign / ad group、impressions、clicks、cost、sales、purchases、units sold。

### 24.6 `amazon_ads_sp_purchased_product_daily`

**表状态：`draft`**  
**第一数据来源：** Ads Reporting v3 `reportTypeId=spPurchasedProduct`

用途：保存广告点击后最终购买的 ASIN，用于分析 halo sales / 跨 ASIN 购买。候选字段包括：`purchased_asin`、`advertised_asin`、`advertised_sku`、campaign / ad group、sales、purchases、units sold。
