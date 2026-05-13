# SellerDataPipeline 数据库唯一事实设计 Spec

> 文档版本：v0.2  
> 更新日期：2026-05-13  
> 当前状态：Azure SQL Database 已开通，但尚未建表；`sql/migrations/` 里的 SQL 暂视为草稿，执行前必须重新对齐本文档。  
> 适用范围：Amazon SP-API Reports / Amazon Ads Reporting / Finances API / 原始数据归档 / 字段取样 / 周报、月报、季度会计数据包。

---

## 0. 本次 v0.2 核心决策

本项目当前处于 **接口取样和数据模型探索阶段**。不要在没有真实 Amazon 样例数据前，把所有业务表和字段一次性建死。

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
| Reports API 采集闭环 | 尚未实现 |
| 当前 SQL migration | 初始草稿，尚未执行 |
| 当前数据库 spec | 本文件 v0.2 |

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
| `amazon_inventory_daily` | `sampling` | Inventory report / FBA inventory source | 库存快照，需确认 FBA 字段口径 |
| `amazon_sales_daily` | `draft` | Business Reports / Sales reports | 销售额、订单数、件数、Sessions 等，需确认 report type |
| `amazon_finance_event` | `draft` | Finances API / settlement reports | 费用、退款、赔偿、仓储费、月租等，需先取样分类 |
| `amazon_ads_daily` | `draft` | Amazon Ads Reporting | Sponsored Products 广告表现，需确认 profile_id 和报表粒度 |
| `amazon_promotion_daily` | `draft` | 财务事件 / 促销报表 / 手动导出 | Coupon、价格折扣、Deal、Prime Day 让利成本 |
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
amazon_sales_daily
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
| 2 | 库存 | Listings/Inventory/FBA inventory 相关报告 | 明确 SKU 库存字段 |
| 3 | 销售和流量 | Business Reports / Sales reports | 确认销售额、订单、sessions 口径 |
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
3. Reports API client 能提交一个 Listing report request。
4. 本地 Sampling Mode 能记录 request manifest。
5. collect 脚本能轮询 `reportId`。
6. 报告 `DONE` 后能下载 raw file。
7. raw file 能保存到 `data/raw/`。
8. 能生成 raw file manifest，包含 path、sha256、row_count、column_count、encoding。
9. 能读取 header，并产出字段样例清单。
10. 根据样例更新本文档中的 L3 业务表字段。

---

## 17. 后续待确认问题

以下问题不阻塞下一阶段取样：

1. 销售日表第一版具体使用哪个 report type。
2. 库存表是否以 FBA 可履约库存为主，还是 Listing quantity 为主。
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
6. 等第一批字段稳定后，再重写 001/002 SQL。
```

这条路线能避免过早设计错误，同时不会阻塞真实接口开发。
