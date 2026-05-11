# Amazon 周度盈亏自动化系统：Serverless 稳定版设计与开发计划

> 版本：v1.1  
> 日期：2026-05-11  
> 适用场景：小体量跨境电商公司，美国 Amazon Seller Central 店铺，当前重点是低成本、稳定、自动化地获取店铺经营数据，并输出周报、月报，以及未来可交给会计/用于报税准备的季度财务数据包。  
> 推荐技术路线：Azure Container Apps Job + Azure SQL Database + Azure Key Vault + Azure Container Registry + Azure Blob Storage + GitHub Actions 部署。

---

## 1. 背景与目标

当前我们希望稳定看到 Amazon 店铺的基础经营与盈亏情况，包括：

- 最近一周卖了多少单、多少件、多少销售额；
- 这段时间广告花了多少钱；
- 优惠券、价格折扣、会员日等活动让利了多少；
- Amazon 平台扣了哪些费用，例如佣金、FBA 配送费、退款、调整、赔偿、仓储费、月租等；
- 算上采购成本、头程成本后，店铺到底是赚钱还是亏钱；
- 尽量减少人工下载报表、手动整理 Excel 的工作；
- 后续可以扩展到月度财务包和季度报税数据包，方便提交给会计进行报税或财务申报准备。

需要特别明确：本系统的季度报表目标是生成 **Tax-ready quarterly package / 季度报税数据包**，也就是把 Amazon 侧销售、退款、平台费用、广告、促销、库存成本、原始报表来源等整理清楚，便于会计复核。它不直接替代会计的最终税务判断，也不自动提交税务申报。最终申报仍需结合公司主体、采购发票、物流发票、银行流水、汇率、税种、当地法规等由会计确认。

本系统不做 Django 后台，不做复杂网页看板，第一阶段直接做一个稳定的 Serverless 数据管道。核心思路从“一个同步 Job 直接请求并等待所有数据”升级为“异步报告任务队列式”：

```text
Amazon SP-API Reports / Amazon Ads Reporting / Finances API
        ↓
提交报告请求 Job：只创建报表任务并记录 report_id
        ↓
报告状态表：追踪 SUBMITTED / IN_QUEUE / IN_PROGRESS / DONE / FAILED
        ↓
采集已完成报告 Job：定时检查、下载、解析、入库
        ↓
Azure SQL Database：存储销售、广告、财务、促销、库存、成本、周期报表快照
        ↓
Azure Blob Storage：归档原始下载报表和生成后的 Excel 报表
        ↓
周期报表 Job：生成周报、月报、季度报税数据包
        ↓
发送到指定邮箱，并记录报表版本与锁账状态
```

---

## 2. 总体决策

### 2.1 推荐最终方案

采用：

```text
Azure Container Apps Job
+ Azure SQL Database
+ Azure Key Vault
+ Azure Container Registry
+ GitHub Actions 自动构建与部署
```

不采用 Django，不把 GitHub Actions 当作长期业务定时器。GitHub Actions 只负责构建 Docker 镜像并部署到 Azure；真正的每日同步、每周周报由 Azure Container Apps Job 执行。

### 2.2 为什么不用 GitHub Actions 直接跑业务任务

GitHub Actions 可以跑定时脚本，但它的主要定位是 CI/CD。作为第一版 MVP 可以用，但长期存在几个问题：

- 定时任务可能延迟，不适合作为稳定业务调度核心；
- GitHub-hosted runner 不在我们自己的 Azure 内部运行环境，网络和密钥治理不如 Azure 原生；
- 业务任务和部署任务混在一起，长期维护容易混乱；
- 后续监控、日志、权限、Key Vault 集成不如 Azure 原生方案自然。

因此最终版采用：

```text
GitHub Actions：代码构建、镜像推送、Azure Job 更新
Azure Container Apps Job：每日/每周真正跑业务脚本
```

### 2.3 为什么优先选 Azure Container Apps Job，而不是 Azure Functions

本项目的任务不是简单的短函数，而是批处理型数据管道：

- 请求 Amazon SP-API 报表；
- 等待报表生成；
- 轮询状态；
- 下载报表；
- 解析 CSV/TSV/JSON；
- upsert 写入数据库；
- 生成 Excel；
- 发送邮件；
- 记录运行日志；
- 失败后重试或下次补算。

这些任务更适合“普通 Python 脚本 + Docker 容器 + 定时运行”的模式。Azure Container Apps Job 正好适合有限时长的批处理任务，任务跑完后停止，不需要常驻服务器。

### 2.4 新增设计原则：异步报告任务队列式

Amazon 的很多报表类接口不是“一次请求立即返回完整数据”，而是异步流程：先提交报表请求，再等待平台生成，完成后再下载。Amazon Ads Reporting v3 也属于类似的异步报表流程。

因此本系统不让一个 Container Apps Job 长时间阻塞等待报表完成，而是拆成三个职责：

```text
1. submit_report_requests
   负责提交报表请求，记录 report_id / report_type / 数据范围。

2. collect_ready_reports
   负责定时检查未完成报告，DONE 后下载、解析、入库。

3. generate_periodic_reports
   负责从数据库生成周报、月报、季度报税数据包，并发邮件。
```

这样做的原因：

- 不浪费容器运行时间在“干等报表”；
- 报告生成快慢不稳定时，系统也能正常恢复；
- 单个报告失败不会阻塞整个同步流程；
- 后续增加新报告类型、月报、季报时不用推翻架构；
- 更容易做运行日志、失败重试、版本追踪和审计。

---

## 3. 关键业务口径

### 3.1 广告归因口径

当前店铺主要投放的是商品广告，也就是 Sponsored Products。

对普通 Seller Central 第三方卖家，Sponsored Products 常用 7 天点击归因口径。也就是说：客户点击广告后，在归因窗口内购买符合规则的商品，广告后台可能把这笔销售归因到该广告点击。

因此本系统使用以下经营口径：

```text
广告类型：Sponsored Products
归因窗口：按 7 天处理
运营快报：最近完整自然周
稳定盈亏：上上个完整自然周
数据回刷：每天回刷最近 45 天
正式财务：月底使用完整月度交易数据复核
```

### 3.2 两类周报

每周一生成两份核心报表。

#### A. 运营快报：最近完整周

用途：看上周经营动作是否正常。

例：如果今天是 2026-05-11 周一，则运营快报看：

```text
2026-05-04 ~ 2026-05-10
```

这份报表用于判断：

- 上周销量是否变好；
- 广告是否烧得太快；
- 优惠券是否带来销量；
- 库存是否下降；
- 下周是否需要调整价格、广告预算、优惠券。

状态标记：

```text
provisional / 运营快报 / 数据未完全稳定
```

#### B. 稳定盈亏：上上个完整周

用途：更接近真实盈亏。

例：如果今天是 2026-05-11 周一，则稳定盈亏看：

```text
2026-04-27 ~ 2026-05-03
```

这份报表用于判断：

- 这一周到底是赚还是亏；
- 广告费占比是否过高；
- 优惠券/促销让利是否过重；
- 退款、费用、赔偿、调整是否异常；
- 每个 SKU 的单件利润大概是多少。

状态标记：

```text
stable / 稳定周报 / 可用于经营复盘
```

---

## 4. 总体架构

### 4.1 架构图

```text
┌─────────────────────────────────────┐
│ GitHub Repository                   │
│ - Python 源码                        │
│ - Dockerfile                         │
│ - SQL migration                      │
│ - GitHub Actions deploy workflow     │
└──────────────────┬──────────────────┘
                   │ push / manual deploy
                   ↓
┌─────────────────────────────────────┐
│ GitHub Actions                      │
│ - build Docker image                 │
│ - push to Azure Container Registry   │
│ - update Azure Container Apps Jobs   │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ Azure Container Registry             │
│ - amazon-profit-report:latest         │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ Azure Container Apps Jobs            │
│                                     │
│ 1. submit-report-requests-job        │
│    每天提交 Amazon 报表生成请求        │
│                                     │
│ 2. collect-ready-reports-job         │
│    每30~60分钟检查并下载完成报告       │
│                                     │
│ 3. generate-periodic-reports-job     │
│    生成周报/月报/季度数据包并发邮件     │
└───────────┬─────────────┬───────────┘
            │             │
            ↓             ↓
┌──────────────────┐  ┌──────────────────┐
│ Azure Key Vault  │  │ Amazon APIs       │
│ - Amazon secrets │  │ - SP-API          │
│ - SQL secrets    │  │ - Ads API         │
│ - Email secrets  │  └──────────────────┘
└──────────┬───────┘
           ↓
┌─────────────────────────────────────┐
│ Azure SQL Database                  │
│ - report request queue               │
│ - raw data                           │
│ - normalized tables                  │
│ - weekly/monthly/quarterly snapshots │
│ - run logs                           │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ Azure Blob Storage                   │
│ - 原始 Amazon 报表归档                │
│ - 生成后的 Excel 报表归档              │
│ - 季度报税数据包归档                  │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ Excel Periodic Reports               │
│ - 周报摘要                           │
│ - 月度财务包                         │
│ - 季度报税数据包                      │
│ - 收入支出拆分                       │
│ - SKU 盈亏                           │
│ - 广告表现                           │
│ - 促销优惠                           │
│ - 库存变化                           │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ Email                               │
│ - 发送给运营/负责人                  │
└─────────────────────────────────────┘
```

### 4.2 Azure 资源清单

建议资源命名：

| 资源 | 建议名称 | 用途 |
|---|---|---|
| Resource Group | `rg-amz-profit-prod` | 统一管理资源 |
| Azure SQL Server | `sql-amz-profit-prod` | SQL Server 逻辑服务器 |
| Azure SQL Database | `sqldb-amz-profit-prod` | 存储业务数据 |
| Azure Key Vault | `kv-amz-profit-prod` | 存储密钥 |
| Azure Container Registry | `acramzprofitprod` | 存储 Docker 镜像 |
| Azure Storage Account | `stamzprofitprod` | 归档原始报表和生成后的 Excel |
| Blob Container | `amazon-raw-reports` | 存放原始下载报表 |
| Blob Container | `amazon-generated-reports` | 存放周报/月报/季度数据包 |
| Container Apps Environment | `cae-amz-profit-prod` | Container Apps 运行环境 |
| Submit Report Job | `job-amz-submit-reports-prod` | 提交 Amazon 报表生成请求 |
| Collect Report Job | `job-amz-collect-reports-prod` | 检查、下载、解析已完成报表 |
| Periodic Report Job | `job-amz-periodic-report-prod` | 生成周报/月报/季度数据包 |
| Log Analytics Workspace | `log-amz-profit-prod` | 查看 Job 日志 |

---

## 5. 数据源设计

### 5.1 Amazon SP-API Reports API

用途：拉取销售、库存、部分业务报表，以及后续月度/季度财务包可能需要的 Settlement、Payments、Tax、Promotion、Coupon 等报表。

Amazon Reports API 的典型流程：

```text
createReport 提交报表请求
    ↓
把 report_id、report_type、日期范围写入 amazon_report_request
    ↓
collect_ready_reports Job 定时调用 getReport 查询处理状态
    ↓
状态为 DONE 后拿 reportDocumentId
    ↓
调用 getReportDocument 获取下载信息
    ↓
下载并解压/解密报表内容
    ↓
原始文件归档到 Blob Storage
    ↓
解析并 upsert 入库
    ↓
标记 parse_status = PARSED
```

注意：不要让一个 Job 提交报告后一直等待几个小时。正确做法是“提交请求”和“检查下载”拆开。

第一版建议优先接入：

| 报表方向 | 用途 | 优先级 |
|---|---|---:|
| Sales and Traffic / Business Reports | 销量、销售额、流量、转化率 | P0 |
| Inventory Report | 库存快照 | P0 |
| Promotions / Coupons | 优惠券、活动让利 | P1 |
| Settlement / Payments 辅助报表 | 月度复核 | P1 |

注意：Amazon 可能会新增字段、变更字段值，所以解析器要允许未知字段，不要因为多了一个字段就失败。

### 5.2 Amazon SP-API Finances API

用途：拉取财务交易事件，包括：

- 商品销售收入；
- Amazon 佣金；
- FBA 配送费；
- 退款；
- 赔偿；
- 调整；
- 其他费用。

它的价值是可以在结算周期关闭前按订单或日期范围获取财务事件，用于周报估算与月度对账。

注意：Finances API 更偏直接分页拉取事件，不一定每个财务数据都必须走 Reports API。实际开发时按两类数据源处理：

```text
异步报表型：SP-API Reports、Ads Reporting v3、部分 Promotion/Coupon/Settlement 报表
直接分页型：Finances API 财务事件、部分库存/订单接口
```

两类数据最终都要进入统一的标准化表和运行日志，区别只是采集方式不同。

### 5.3 Amazon Ads API

用途：拉取 Sponsored Products 广告表现。

Amazon Ads Reporting v3 也属于异步报表思路：创建广告报表请求、查询状态、下载报表文件。实现上可以复用 `amazon_report_request` 的状态管理，只是 `source_system` 标记为 `ads_reporting`，并使用 Ads API 自己的 report id / status / download URL 字段。

第一版建议以日维度为主：

| 维度 | 用途 |
|---|---|
| campaign | 看广告活动层级花费与销售 |
| ad group | 看广告组表现 |
| target / keyword | 看关键词/投放对象表现 |
| advertised product / purchased product | 看广告商品与购买商品关系，后续优化用 |

核心字段：

```text
impressions
clicks
cost / spend
sales
purchases / orders
acos
roas
campaign_id
campaign_name
ad_group_id
keyword / target
sku / asin
```

### 5.4 手动维护成本数据

Amazon 不知道我们的采购成本、头程成本、包装成本，因此必须维护一张成本表。

第一版可以通过 SQL 表手动录入，后续再做 Excel 上传或简单管理页面。

---

## 6. 时间窗口与定时任务

### 6.1 统一时区

- 系统内部建议全部存 UTC 时间；
- 业务报表按店铺 marketplace 时区或指定业务时区计算；
- 本项目建议业务周按英国时间 Europe/London 计算，但 Amazon 美国站数据本身可能按站点/报表口径输出，因此每种报表的时间字段需要明确记录原始时区与标准化日期。

Container Apps Job 的 cron 表达式按 UTC 计算，因此不要直接写“伦敦早上 9 点”而忘记夏令时问题。建议：

- Job 按 UTC 固定时间运行；
- Python 内部用 `Europe/London` 计算业务周；
- 周报标题中明确展示自然日期。

### 6.2 提交报告请求任务

Job：

```text
job-amz-submit-reports-prod
```

建议时间：

```text
每天 UTC 02:23
```

任务内容：

```text
python scripts/submit_report_requests.py --days 45
```

执行逻辑：

1. 计算最近 45 天日期范围；
2. 根据配置生成需要请求的 report_type 列表；
3. 对每个 report_type + marketplace + 日期范围调用 createReport 或 Ads create report；
4. 将 report_id、report_type、数据范围、marketplace、requested_at 写入 `amazon_report_request`；
5. 初始状态标记为 `SUBMITTED`；
6. 如果同一 report_type + 日期范围已经有未过期的成功请求，避免重复提交；
7. 写入运行日志。

这个 Job 只提交请求，不等待报告完成。

### 6.3 检查并下载已完成报告任务

Job：

```text
job-amz-collect-reports-prod
```

建议频率：

```text
每 30 分钟或每 1 小时运行一次
```

任务内容：

```text
python scripts/collect_ready_reports.py --max-items 20
```

执行逻辑：

1. 从 `amazon_report_request` 查找未完成报告；
2. 对 `SUBMITTED / IN_QUEUE / IN_PROGRESS` 状态调用状态查询接口；
3. 如果仍未完成，更新 `last_checked_at` 后退出；
4. 如果状态为 `DONE`，获取 `report_document_id`；
5. 下载报告文件，必要时解压/解密；
6. 将原始文件存到 Azure Blob Storage；
7. 根据 report_type 调用对应 parser；
8. 将标准化数据 upsert 到 Azure SQL；
9. 标记 `download_status = DOWNLOADED`、`parse_status = PARSED`；
10. 如果状态为 `FATAL / CANCELLED`，记录失败，不无限重试。

这种设计比“提交后固定等待几小时”更稳，因为不同报告生成时间受报告大小、系统负载、队列等影响，并不固定。

### 6.4 生成周期报表任务

Job：

```text
job-amz-periodic-report-prod
```

建议时间：

```text
每周一 UTC 08:17：生成周报
每月 3 日 UTC 08:37：生成上月月度财务包初版
每季度结束后第 7 天 UTC 09:17：生成季度报税数据包初版
每季度结束后第 14 天 UTC 09:17：生成季度报税数据包稳定版
```

命令示例：

```text
python scripts/generate_periodic_report.py --period weekly
python scripts/generate_periodic_report.py --period monthly --mode draft
python scripts/generate_periodic_report.py --period quarterly --mode draft
python scripts/generate_periodic_report.py --period quarterly --mode stable
```

周报输出：

1. 最近完整周运营快报；
2. 上上完整周稳定盈亏报；
3. Excel 附件；
4. 邮件摘要；
5. 周报发送日志。

月报输出：

1. 上月收入支出拆分；
2. 月度广告、促销、退款、赔偿、平台费用汇总；
3. 月度 SKU 盈亏；
4. 与 settlement / transaction / finance 口径的对账 Sheet；
5. 会计用月度财务包。

季度报税数据包输出：

1. 季度销售收入明细；
2. 季度退款明细；
3. Amazon 平台费用明细；
4. 广告费明细；
5. 促销/优惠券明细；
6. 赔偿/调整明细；
7. 期初库存、期末库存、季度销量；
8. COGS / 销售成本估算；
9. 原始报表来源、report_id、生成时间、数据状态；
10. 会计复核提示和人工调整项。

### 6.5 手动补跑任务

保留手动命令：

```bash
python scripts/submit_report_requests.py --start 2026-04-01 --end 2026-04-30
python scripts/collect_ready_reports.py --report-id xxx
python scripts/generate_periodic_report.py --period weekly --week-start 2026-04-27
python scripts/generate_periodic_report.py --period quarterly --year 2026 --quarter 2 --mode draft
```

同时保留 Azure CLI 手动触发 Job 的能力，用于失败重跑、历史数据回填和会计临时要求。

---

## 7. 数据库设计

### 7.1 设计原则

- 原始数据和标准化数据都保留；
- 所有外部数据写入都要 upsert，不能简单 insert；
- 每张核心明细表都要有唯一键，防止回刷导致重复计算；
- 所有金额字段记录 currency；
- 所有运行任务都记录 run log；
- 周报结果写入 snapshot 表，便于对比历史版本。

### 7.2 报告请求状态表：`amazon_report_request`

用途：追踪所有 Amazon 异步报表请求，是本系统“异步报告任务队列式”的核心表。

字段建议：

```sql
CREATE TABLE amazon_report_request (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    marketplace NVARCHAR(50) NOT NULL,
    source_system NVARCHAR(50) NOT NULL, -- sp_api_reports / ads_reporting / other
    report_type NVARCHAR(200) NOT NULL,
    data_start_time DATETIME2 NOT NULL,
    data_end_time DATETIME2 NOT NULL,
    report_id NVARCHAR(300) NOT NULL,
    report_document_id NVARCHAR(300) NULL,
    processing_status NVARCHAR(50) NOT NULL, -- SUBMITTED / IN_QUEUE / IN_PROGRESS / DONE / FATAL / CANCELLED
    download_status NVARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING / DOWNLOADED / FAILED / SKIPPED
    parse_status NVARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING / PARSED / FAILED / NO_DATA
    requested_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    last_checked_at DATETIME2 NULL,
    completed_at DATETIME2 NULL,
    downloaded_at DATETIME2 NULL,
    parsed_at DATETIME2 NULL,
    retry_count INT NOT NULL DEFAULT 0,
    raw_file_path NVARCHAR(1000) NULL,
    checksum NVARCHAR(200) NULL,
    error_message NVARCHAR(MAX) NULL,
    source_run_id BIGINT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

唯一键建议：

```text
marketplace + source_system + report_type + data_start_time + data_end_time + report_id
```

状态说明：

```text
SUBMITTED：已提交请求
IN_QUEUE / IN_PROGRESS：Amazon 正在生成
DONE：Amazon 已生成，可获取 document
FATAL / CANCELLED：Amazon 端失败或取消
DOWNLOADED：文件已下载并归档
PARSED：文件已解析并入库
FAILED：下载或解析失败
NO_DATA：报告成功但无有效数据
```

### 7.3 成本表：`amazon_sku_cost`

用途：维护采购、头程、包装等单件成本。

字段建议：

```sql
CREATE TABLE amazon_sku_cost (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    marketplace NVARCHAR(50) NOT NULL,
    sku NVARCHAR(100) NOT NULL,
    asin NVARCHAR(20) NULL,
    product_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    first_mile_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    packaging_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    other_unit_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    currency NVARCHAR(10) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    remark NVARCHAR(500) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

唯一键建议：

```text
marketplace + sku + effective_from
```

### 7.4 销售日表：`amazon_sales_daily`

用途：记录每日 SKU/ASIN 销售与流量表现。

字段建议：

```sql
CREATE TABLE amazon_sales_daily (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    marketplace NVARCHAR(50) NOT NULL,
    sales_date DATE NOT NULL,
    sku NVARCHAR(100) NOT NULL,
    asin NVARCHAR(20) NULL,
    ordered_units INT NOT NULL DEFAULT 0,
    ordered_orders INT NOT NULL DEFAULT 0,
    ordered_product_sales DECIMAL(18,4) NOT NULL DEFAULT 0,
    sessions INT NULL,
    conversion_rate DECIMAL(18,6) NULL,
    buy_box_percentage DECIMAL(18,6) NULL,
    currency NVARCHAR(10) NOT NULL,
    raw_data NVARCHAR(MAX) NULL,
    source_run_id BIGINT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

唯一键建议：

```text
marketplace + sales_date + sku
```

### 7.5 财务事件表：`amazon_finance_event`

用途：记录 Amazon 财务事件明细。

字段建议：

```sql
CREATE TABLE amazon_finance_event (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    marketplace NVARCHAR(50) NOT NULL,
    event_id NVARCHAR(200) NOT NULL,
    posted_date DATETIME2 NOT NULL,
    order_id NVARCHAR(100) NULL,
    sku NVARCHAR(100) NULL,
    asin NVARCHAR(20) NULL,
    event_type NVARCHAR(100) NOT NULL,
    amount_type NVARCHAR(100) NULL,
    amount_description NVARCHAR(300) NULL,
    amount DECIMAL(18,4) NOT NULL,
    currency NVARCHAR(10) NOT NULL,
    raw_data NVARCHAR(MAX) NULL,
    source_run_id BIGINT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

唯一键建议：

```text
marketplace + event_id
```

如果 Amazon 返回内容没有稳定 event_id，则使用以下字段生成 hash：

```text
marketplace + posted_date + order_id + event_type + amount_type + amount_description + amount + currency
```

### 7.6 广告日表：`amazon_ads_daily`

用途：记录 Sponsored Products 日维度广告表现。

字段建议：

```sql
CREATE TABLE amazon_ads_daily (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    marketplace NVARCHAR(50) NOT NULL,
    profile_id NVARCHAR(100) NOT NULL,
    ads_date DATE NOT NULL,
    campaign_id NVARCHAR(100) NULL,
    campaign_name NVARCHAR(300) NULL,
    ad_group_id NVARCHAR(100) NULL,
    ad_group_name NVARCHAR(300) NULL,
    targeting_text NVARCHAR(500) NULL,
    match_type NVARCHAR(100) NULL,
    sku NVARCHAR(100) NULL,
    asin NVARCHAR(20) NULL,
    impressions INT NOT NULL DEFAULT 0,
    clicks INT NOT NULL DEFAULT 0,
    spend DECIMAL(18,4) NOT NULL DEFAULT 0,
    ad_sales DECIMAL(18,4) NOT NULL DEFAULT 0,
    ad_orders INT NOT NULL DEFAULT 0,
    acos DECIMAL(18,6) NULL,
    roas DECIMAL(18,6) NULL,
    currency NVARCHAR(10) NOT NULL,
    raw_data NVARCHAR(MAX) NULL,
    source_run_id BIGINT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

唯一键建议：

```text
marketplace + profile_id + ads_date + campaign_id + ad_group_id + targeting_text + sku + asin
```

### 7.7 促销/优惠券日表：`amazon_promotion_daily`

用途：记录 Coupon、Price Discount、Deal 等促销表现。

字段建议：

```sql
CREATE TABLE amazon_promotion_daily (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    marketplace NVARCHAR(50) NOT NULL,
    promo_date DATE NOT NULL,
    promotion_id NVARCHAR(100) NULL,
    promotion_name NVARCHAR(300) NULL,
    promotion_type NVARCHAR(100) NOT NULL,
    sku NVARCHAR(100) NULL,
    asin NVARCHAR(20) NULL,
    discount_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
    redeemed_units INT NOT NULL DEFAULT 0,
    fee_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
    currency NVARCHAR(10) NOT NULL,
    raw_data NVARCHAR(MAX) NULL,
    source_run_id BIGINT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

### 7.8 库存快照表：`amazon_inventory_daily`

用途：记录每日库存快照。

字段建议：

```sql
CREATE TABLE amazon_inventory_daily (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    marketplace NVARCHAR(50) NOT NULL,
    inventory_date DATE NOT NULL,
    sku NVARCHAR(100) NOT NULL,
    asin NVARCHAR(20) NULL,
    available_quantity INT NULL,
    reserved_quantity INT NULL,
    inbound_quantity INT NULL,
    fulfillable_quantity INT NULL,
    raw_data NVARCHAR(MAX) NULL,
    source_run_id BIGINT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

唯一键建议：

```text
marketplace + inventory_date + sku
```

### 7.9 周报快照表：`amazon_weekly_profit_snapshot`

用途：保存系统计算后的周报结果。

字段建议：

```sql
CREATE TABLE amazon_weekly_profit_snapshot (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    marketplace NVARCHAR(50) NOT NULL,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    report_type NVARCHAR(50) NOT NULL, -- quick / stable / monthly
    data_status NVARCHAR(50) NOT NULL, -- provisional / stable / final
    sales_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
    units_sold INT NOT NULL DEFAULT 0,
    orders_count INT NOT NULL DEFAULT 0,
    reimbursement_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
    amazon_referral_fees DECIMAL(18,4) NOT NULL DEFAULT 0,
    fba_fees DECIMAL(18,4) NOT NULL DEFAULT 0,
    refund_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
    ad_spend DECIMAL(18,4) NOT NULL DEFAULT 0,
    ad_sales DECIMAL(18,4) NOT NULL DEFAULT 0,
    promotion_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    product_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    first_mile_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    packaging_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    other_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    estimated_profit DECIMAL(18,4) NOT NULL DEFAULT 0,
    profit_per_unit DECIMAL(18,4) NULL,
    acos DECIMAL(18,6) NULL,
    tacos DECIMAL(18,6) NULL,
    ending_inventory INT NULL,
    currency NVARCHAR(10) NOT NULL,
    calculation_version NVARCHAR(50) NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

唯一键建议：

```text
marketplace + week_start + week_end + report_type + calculation_version
```

### 7.10 运行日志表：`amazon_sync_run_log`

用途：记录每次同步任务的状态。

字段建议：

```sql
CREATE TABLE amazon_sync_run_log (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    job_name NVARCHAR(100) NOT NULL,
    job_execution_id NVARCHAR(200) NULL,
    status NVARCHAR(50) NOT NULL, -- running / success / failed / partial_success
    started_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    finished_at DATETIME2 NULL,
    date_start DATE NULL,
    date_end DATE NULL,
    message NVARCHAR(MAX) NULL,
    error_detail NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

### 7.11 报表发送日志表：`amazon_periodic_report_log`

用途：记录每次周报、月报、季度报税数据包的生成、归档与邮件发送状态。

字段建议：

```sql
CREATE TABLE amazon_periodic_report_log (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    period_type NVARCHAR(50) NOT NULL, -- weekly / monthly / quarterly
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    report_type NVARCHAR(50) NOT NULL, -- quick / stable / monthly_finance / quarterly_tax_package
    version NVARCHAR(50) NOT NULL DEFAULT 'v1',
    status NVARCHAR(50) NOT NULL, -- draft / stable / locked / amended / failed
    file_name NVARCHAR(300) NULL,
    blob_path NVARCHAR(1000) NULL,
    receiver_email NVARCHAR(300) NULL,
    email_sent BIT NOT NULL DEFAULT 0,
    locked_at DATETIME2 NULL,
    approved_by NVARCHAR(200) NULL,
    approved_at DATETIME2 NULL,
    message NVARCHAR(MAX) NULL,
    error_detail NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

季度报税数据包需要保留版本和锁账状态，避免后续回刷数据时覆盖会计已使用的版本。

### 7.12 周期财务快照表：`amazon_periodic_finance_snapshot`

用途：统一保存月度、季度级别的财务汇总快照。周报可以继续保留在 `amazon_weekly_profit_snapshot`，月报/季报建议进入周期快照表。

字段建议：

```sql
CREATE TABLE amazon_periodic_finance_snapshot (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    marketplace NVARCHAR(50) NOT NULL,
    period_type NVARCHAR(50) NOT NULL, -- monthly / quarterly
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    version NVARCHAR(50) NOT NULL,
    status NVARCHAR(50) NOT NULL, -- draft / stable / locked / amended
    sales_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
    reimbursement_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
    refund_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
    amazon_fees DECIMAL(18,4) NOT NULL DEFAULT 0,
    fba_fees DECIMAL(18,4) NOT NULL DEFAULT 0,
    storage_fees DECIMAL(18,4) NOT NULL DEFAULT 0,
    subscription_fees DECIMAL(18,4) NOT NULL DEFAULT 0,
    ad_spend DECIMAL(18,4) NOT NULL DEFAULT 0,
    promotion_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    product_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    first_mile_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    packaging_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    other_cost DECIMAL(18,4) NOT NULL DEFAULT 0,
    estimated_profit DECIMAL(18,4) NOT NULL DEFAULT 0,
    currency NVARCHAR(10) NOT NULL,
    calculation_version NVARCHAR(50) NOT NULL,
    locked_at DATETIME2 NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

唯一键建议：

```text
marketplace + period_type + period_start + period_end + version
```

---

## 8. 利润计算逻辑

### 8.1 基础公式

第一版周报使用估算利润口径：

```text
估算利润
= 商品销售收入
+ 赔偿/调整收入
- Amazon 佣金
- FBA 配送费
- 退款损失
- 广告花费
- 优惠券/促销成本
- 商品采购成本
- 头程成本
- 包装成本
- 其他单件成本
- 其他固定/一次性支出分摊
```

### 8.2 广告费避免重复计算

第一版规则：

```text
周报中的广告费使用 Amazon Ads API 的 spend。
如果 Finances / Payments 中也出现广告扣费，周报计算中不重复扣除，只在对账 Sheet 里展示。
```

月度财务复核时，可以将 Ads API spend 和 Payments 中广告账单做对账，发现差异后人工确认。

### 8.3 活动费与优惠券

促销成本可能来自：

- Coupon 折扣；
- Coupon redemption fee；
- Price Discount；
- Prime Day / Deal / Promotion；
- Transaction 明细中的 promotion rebate / discount。

第一版处理原则：

```text
能从 Promotion/Coupon 报告明确拿到的，用该报告。
拿不到或不稳定的，从 Finance Event 中按 amount_description 分类。
最终需要在 Excel 里单独展示“促销/优惠券成本”，不要混在 Amazon Fees 里。
```

### 8.4 固定费用处理

固定费用包括：

- Professional Selling Plan 月租；
- 仓储费；
- 长期仓储费；
- 软件服务费；
- 一次性服务费。

第一版建议：

- 如果费用能按交易日期获取，按费用 posted_date 归入对应周；
- 如果是月度费用，但希望更平滑看周利润，可额外做“月度费用按周分摊”字段；
- Excel 里同时展示：
  - 按实际发生日期扣费；
  - 按周分摊后的管理口径。

### 8.5 SKU 级别利润

SKU 级别第一版可以这样算：

```text
SKU 估算利润
= SKU 商品销售收入
- SKU Amazon 费用
- SKU FBA 费用
- SKU 退款损失
- SKU 分摊广告费
- SKU 促销成本
- SKU 销量 × 单件采购成本
- SKU 销量 × 单件头程成本
- SKU 销量 × 单件包装成本
```

广告费归属规则：

- 如果 Ads report 里有 SKU/ASIN，直接归属；
- 如果只有 campaign 级别，先归属到 campaign 对应主推 SKU；
- 如果无法归属，放到“未分配广告费”，在总利润中扣除，但 SKU 利润不强行分摊。

### 8.6 月度与季度报税数据包口径

月度、季度报表比周报更接近会计用途，需要区分三层口径：

```text
第一层：运营盈亏口径
用于运营复盘，重点看销售、广告、促销、SKU 盈亏。

第二层：会计财务包口径
用于交给会计复核，需要收入、退款、平台费用、广告费、库存成本、原始来源、人工调整项。

第三层：最终税务申报口径
不由本系统自动决定，需要会计结合公司账务、发票、银行流水、税法和汇率确认。
```

季度报税数据包必须至少包含：

- 销售收入明细与汇总；
- 退款明细与汇总；
- Amazon 平台费用明细与分类；
- FBA 配送费、仓储费、订阅费、调整、赔偿；
- 广告费明细；
- 优惠券/促销成本明细；
- SKU 销量与销售成本 COGS；
- 期初库存、期末库存、期间销量；
- 原始报告 ID、文件归档路径、生成时间；
- 缺失成本、未分类费用、汇率/税务人工确认项。

### 8.7 锁账与版本机制

周报可以每天随数据回刷而变化，但月度和季度报表不能无限自动覆盖。建议流程：

```text
月度：
月初第 3 天生成 draft 版
月初第 7~10 天生成 stable 版
会计确认后标记 locked
如需修改，生成 amended 版，不覆盖 locked 版

季度：
季度结束后第 7 天生成 draft 版
季度结束后第 14 天生成 stable 版
会计确认后标记 locked
如需修改，生成 amended 版，不覆盖 locked 版
```

锁账后，该周期报表和对应 Excel 文件不再被自动覆盖，只能新增修正版。这样以后可以追溯：会计或报税使用的是哪一个版本、哪个时间生成、对应哪些 Amazon 原始报表。

---

## 9. Excel 报表设计

每周邮件附件建议命名：

```text
Amazon_Weekly_Profit_Report_2026-05-04_to_2026-05-10.xlsx
```

Sheet 设计：

### 9.1 `01_周报摘要`

内容：

| 模块 | 指标 |
|---|---|
| 报表时间 | 最近完整周、上上完整周 |
| 销售 | 销售额、订单数、销量 |
| 广告 | 花费、广告销售额、ACOS、TACOS |
| 费用 | Amazon 费用、FBA 费用、退款、促销成本 |
| 成本 | 采购成本、头程成本、包装成本 |
| 利润 | 估算利润、单件利润、利润率 |
| 数据状态 | provisional / stable |

### 9.2 `02_收入支出拆分`

展示：

- 商品销售收入；
- 赔偿/调整收入；
- Amazon 佣金；
- FBA 配送费；
- 退款；
- 广告花费；
- 促销/优惠券；
- 仓储/月租/其他费用；
- 采购/头程/包装成本；
- 估算利润。

### 9.3 `03_SKU盈亏`

每个 SKU 一行：

```text
SKU
ASIN
商品名，可后续补充
销量
订单数
销售额
广告费
促销成本
Amazon 费用
FBA 费用
退款
采购成本
头程成本
估算利润
单件利润
期末库存
```

### 9.4 `04_广告表现`

展示：

```text
campaign_name
ad_group_name
targeting_text
impressions
clicks
CPC
spend
ad_sales
orders
ACOS
ROAS
```

### 9.5 `05_促销优惠`

展示：

```text
promotion_type
promotion_name
sku
asin
redeemed_units
discount_amount
fee_amount
total_promotion_cost
```

### 9.6 `06_库存变化`

展示：

```text
sku
asin
期初库存
期末库存
本周销量
预计还能卖几周
```

### 9.7 `07_数据校验`

展示：

- 本次同步运行时间；
- 拉取数据范围；
- 哪些 API 成功/失败；
- 是否存在缺失成本的 SKU；
- 是否存在无法归类的费用；
- Ads spend 与 Finance 广告扣费差异；
- 是否有异常大额退款或调整。


### 9.8 月度财务包 Excel

建议命名：

```text
Amazon_Monthly_Finance_Package_2026-04_v1_draft.xlsx
Amazon_Monthly_Finance_Package_2026-04_v1_locked.xlsx
```

建议 Sheet：

```text
01_月度摘要
02_收入明细
03_退款明细
04_Amazon费用分类
05_广告费用
06_促销优惠
07_SKU销售成本
08_库存变化
09_对账校验
10_人工调整项
```

### 9.9 季度报税数据包 Excel

建议命名：

```text
Amazon_Quarterly_Tax_Package_2026_Q2_v1_draft.xlsx
Amazon_Quarterly_Tax_Package_2026_Q2_v1_stable.xlsx
Amazon_Quarterly_Tax_Package_2026_Q2_v1_locked.xlsx
```

建议 Sheet：

```text
01_季度摘要
02_销售收入明细
03_退款明细
04_Amazon平台费用
05_FBA与仓储费用
06_广告费用明细
07_促销优惠明细
08_赔偿与调整
09_SKU销量与COGS
10_期初期末库存
11_原始报告索引
12_缺失与异常提示
13_人工调整项
14_会计复核说明
```

季度报税数据包首页必须注明：

```text
本文件为 Amazon 侧经营与财务数据整理包，用于会计复核和报税准备。
最终税务申报仍需结合公司账务、采购发票、物流发票、银行流水、汇率和当地税务规则确认。
```

---

## 10. 项目代码结构

建议仓库名：

```text
amazon-profit-report
```

目录结构：

```text
amazon-profit-report/
  README.md
  Dockerfile
  requirements.txt
  pyproject.toml                  # 可选
  .env.example

  sql/
    001_create_tables.sql
    002_create_indexes.sql
    003_seed_cost_template.sql

  src/
    config.py

    amazon/
      __init__.py
      auth.py                     # LWA token、签名、通用认证
      sp_api_client.py             # SP-API 基础客户端
      ads_api_client.py            # Ads API 基础客户端
      report_requester.py          # 提交异步报表请求
      report_collector.py           # 查询状态、下载、归档、分发解析
      report_poller.py             # 兼容/通用状态查询工具，可被 collector 使用
      sales_reports.py             # 销售报表解析
      finance_events.py            # 财务事件解析
      ads_reports.py               # 广告报表解析
      promotion_reports.py         # 促销/优惠券解析
      inventory_reports.py         # 库存解析

    db/
      __init__.py
      azure_sql.py                 # SQL 连接
      upsert.py                    # MERGE / upsert 工具
      repositories.py              # 各表读写封装

    services/
      __init__.py
      submit_report_requests.py     # 提交报表请求主服务
      collect_ready_reports.py      # 下载并解析已完成报表主服务
      calculate_weekly_profit.py    # 周利润计算
      calculate_periodic_finance.py # 月度/季度财务包计算
      generate_excel.py             # Excel 生成
      send_email.py                 # 邮件发送
      validation.py                 # 数据校验

    utils/
      __init__.py
      date_windows.py               # 周窗口、45天回刷窗口
      money.py                      # 金额格式化、汇率预留
      logger.py                     # 日志封装
      retry.py                      # 指数退避重试
      hash_key.py                   # 生成事件唯一键

  scripts/
    submit_report_requests.py
    collect_ready_reports.py
    generate_periodic_report.py
    generate_weekly_report.py       # 可作为 generate_periodic_report --period weekly 的薄封装
    backfill.py
    test_connection.py

  tests/
    test_date_windows.py
    test_profit_calculation.py
    test_upsert.py

  .github/
    workflows/
      deploy_container_jobs.yml
```

---

## 11. 配置与密钥管理

### 11.1 配置原则

不把任何密钥写入代码仓库。

敏感信息包括：

```text
Amazon LWA Client ID
Amazon LWA Client Secret
Amazon SP-API Refresh Token
Amazon Ads Refresh Token
Amazon AWS Access Key / Secret Key，如仍需要
Azure SQL 连接信息
SMTP 密码 / Graph API 凭证
```

### 11.2 Key Vault Secret 建议

Key Vault 中建议存：

```text
AMAZON_LWA_CLIENT_ID
AMAZON_LWA_CLIENT_SECRET
AMAZON_SP_API_REFRESH_TOKEN
AMAZON_ADS_REFRESH_TOKEN
AMAZON_AWS_ACCESS_KEY_ID
AMAZON_AWS_SECRET_ACCESS_KEY
AZURE_SQL_CONNECTION_STRING
AZURE_STORAGE_CONNECTION_STRING
AZURE_BLOB_RAW_REPORT_CONTAINER
AZURE_BLOB_GENERATED_REPORT_CONTAINER
EMAIL_SMTP_HOST
EMAIL_SMTP_PORT
EMAIL_SMTP_USER
EMAIL_SMTP_PASSWORD
REPORT_RECEIVER_EMAIL
```

Container Apps Job 使用 Managed Identity 读取 Key Vault。代码使用 Azure Identity SDK 获取 secret。

### 11.3 GitHub Actions 与 Azure

GitHub Actions 用于部署。推荐使用 OIDC 登录 Azure，避免在 GitHub Secrets 中长期保存 Azure Service Principal 密钥。

GitHub Actions 需要做：

1. 登录 Azure；
2. 构建 Docker 镜像；
3. 推送到 Azure Container Registry；
4. 更新 Container Apps Job 的镜像版本。

---

## 12. Docker 与运行方式

### 12.1 Dockerfile 示例

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app

CMD ["python", "scripts/collect_ready_reports.py", "--max-items", "20"]
```

注意：如果使用 `pyodbc` 连接 Azure SQL，需要安装 Microsoft ODBC Driver。第一版也可以使用 `pymssql` 或 SQLAlchemy，但正式稳定建议使用官方 ODBC Driver + pyodbc。

### 12.2 本地运行

```bash
python scripts/test_connection.py
python scripts/submit_report_requests.py --days 45
python scripts/collect_ready_reports.py --max-items 20
python scripts/generate_periodic_report.py --period weekly
```

### 12.3 容器运行

```bash
docker build -t amazon-profit-report:local .
docker run --env-file .env amazon-profit-report:local python scripts/submit_report_requests.py --days 45
docker run --env-file .env amazon-profit-report:local python scripts/collect_ready_reports.py --max-items 20
```

---

## 13. Azure Container Apps Job 配置建议

三个 Job 可以使用同一个 Docker 镜像，只是 command 不同。

### 13.1 Submit Report Requests Job

建议配置：

```text
name: job-amz-submit-reports-prod
trigger: Schedule
cron: 23 2 * * *
replica timeout: 1800 或 3600 秒
replica retry limit: 1 或 2
cpu: 0.5
memory: 1Gi
command: python scripts/submit_report_requests.py --days 45
```

职责：只提交报表请求并写入 `amazon_report_request`，不等待报告完成。

### 13.2 Collect Ready Reports Job

建议配置：

```text
name: job-amz-collect-reports-prod
trigger: Schedule
cron: */30 * * * *
replica timeout: 1800 或 3600 秒
replica retry limit: 1
cpu: 0.5 ~ 1.0
memory: 1Gi ~ 2Gi
command: python scripts/collect_ready_reports.py --max-items 20
```

职责：检查未完成报告，DONE 后下载、归档、解析、入库。

### 13.3 Periodic Report Job

建议配置：

```text
name: job-amz-periodic-report-prod
trigger: Schedule
cron: 17 8 * * 1
replica timeout: 1800 或 3600 秒
replica retry limit: 1
cpu: 0.5
memory: 1Gi
command: python scripts/generate_periodic_report.py --period weekly
```

如果一个 Container Apps Job 只能配置一个固定命令，可以为同一个镜像创建多个报表 Job：

```text
job-amz-weekly-report-prod      command: python scripts/generate_periodic_report.py --period weekly
job-amz-monthly-report-prod     command: python scripts/generate_periodic_report.py --period monthly --mode draft
job-amz-quarterly-report-prod   command: python scripts/generate_periodic_report.py --period quarterly --mode draft
```

### 13.4 Manual Backfill Job，可选

后续可增加一个手动 Job：

```text
name: job-amz-backfill-prod
trigger: Manual
command: python scripts/backfill.py
```

用于手动补历史数据、重新生成某月/某季度报表。

---

## 14. 错误处理与重试

### 14.1 API 重试

对以下情况使用指数退避重试：

- HTTP 429 rate limit；
- HTTP 500/502/503/504；
- 网络连接错误；
- Amazon 报表状态暂未完成。

不应无限重试。建议：

```text
单个 API 调用最多重试 3~5 次
collect_ready_reports 每次只检查有限数量的 pending report
未完成报告更新 last_checked_at 后退出，不长时间等待
超过最大尝试次数仍失败则标记 FAILED，等待人工检查或手动补跑
```

### 14.2 数据缺失处理

周报生成前做校验：

- 最近完整周是否有销售数据；
- 广告数据是否存在；
- 财务数据是否存在；
- 成本表是否缺 SKU；
- 是否存在未分类费用；
- 是否存在异常大额退款/调整。

如果数据不完整，不要默默生成“看起来正常”的报表。Excel 摘要页必须提示：

```text
数据状态：部分数据缺失，请谨慎解读
```

### 14.3 幂等设计

所有同步任务都必须支持重复执行。

也就是说，同一个日期范围重复跑 10 次，数据库里的结果不应该重复增加，只能更新已有记录。

关键措施：

- 所有明细表设计唯一键；
- 使用 MERGE / upsert；
- 周报 snapshot 带 calculation_version；
- 运行日志记录每次执行。

---

## 15. 开发计划

### Phase 0：账号、权限、资源准备

目标：确保基础资源和 API 权限可用。

任务：

1. 确认 Amazon SP-API 开发者应用权限；
2. 获取 SP-API refresh token；
3. 获取 Ads API refresh token 和 profile_id；
4. 创建 Azure Resource Group；
5. 创建 Azure SQL Database 免费版；
6. 创建 Azure Key Vault；
7. 创建 Azure Container Registry；
8. 创建 Container Apps Environment；
9. 创建 Log Analytics Workspace；
10. 配置 Managed Identity 与 Key Vault 访问权限。

验收：

- 本地脚本能读取 Key Vault 测试 secret；
- 本地脚本能连接 Azure SQL；
- 本地脚本能获取 Amazon access token；
- Azure Container Apps Job 能启动一个 hello-world 容器。

### Phase 1：项目骨架与数据库

目标：完成代码项目基础结构和数据库 schema。

任务：

1. 初始化 GitHub 仓库；
2. 创建 Python 项目结构；
3. 编写 Dockerfile；
4. 编写 SQL 建表脚本；
5. 编写 Azure SQL 连接工具；
6. 编写 upsert 工具；
7. 编写 run log 写入工具；
8. 编写日期窗口工具。

验收：

- `python scripts/test_connection.py` 成功；
- 数据库表创建成功；
- 测试数据 upsert 不重复；
- Docker 镜像本地可运行。

### Phase 2：Amazon 异步报告队列与数据采集

目标：建立“提交报告请求 → 检查状态 → 下载归档 → 解析入库”的异步数据采集流程。

任务：

1. 实现 Amazon LWA token 获取；
2. 实现 SP-API 签名请求；
3. 实现 `amazon_report_request` 读写；
4. 实现 `submit_report_requests.py`，可提交销售、库存、Promotion/Coupon、Settlement/Payments 等报告请求；
5. 实现 Ads Reporting v3 报告请求；
6. 实现 `collect_ready_reports.py`，可检查状态、下载文件、归档 Blob、调用 parser；
7. 实现销售报表解析入库；
8. 实现库存报表解析入库；
9. 实现 Finances API 财务事件直接分页拉取与入库；
10. 实现 Ads API 报表下载、解析入库；
11. 实现促销/优惠券数据解析入库。

验收：

- 可提交最近 7 天销售报表请求；
- 报告状态可在 `amazon_report_request` 中更新；
- DONE 报告可下载、归档、解析并入库；
- 可同步最近 7 天广告数据；
- 可同步最近 7 天财务事件；
- 可同步库存快照；
- 重复执行不会重复插入；
- 错误会记录到 `amazon_sync_run_log` 和 `amazon_report_request`。


### Phase 3：利润计算与周报快照

目标：自动计算运营快报和稳定盈亏。

任务：

1. 实现最近完整周计算；
2. 实现上上完整周计算；
3. 实现 SKU 成本匹配；
4. 实现收入/支出分类；
5. 实现广告费去重规则；
6. 实现促销成本归类；
7. 实现周报 snapshot 写入；
8. 实现数据校验与异常提示。

验收：

- 能生成指定周的利润快照；
- 快照结果与手动 Excel 抽样核对基本一致；
- 缺少 SKU 成本时会提示，不会假装利润准确；
- 广告费不会重复扣除。

### Phase 4：Excel 周报/月报/季度数据包生成与邮件发送

目标：自动生成可读性强、可追溯的周期报表。

任务：

1. 使用 openpyxl 生成 Excel；
2. 创建周报 Sheet；
3. 创建月度财务包 Sheet；
4. 创建季度报税数据包 Sheet；
5. 添加金额格式、百分比格式、冻结窗格、筛选；
6. 添加摘要页、数据校验页、原始报告索引页、人工调整项页；
7. 将生成后的 Excel 归档到 Azure Blob Storage；
8. 实现 SMTP 或 Microsoft Graph 发邮件；
9. 记录 `amazon_periodic_report_log`。

验收：

- `python scripts/generate_periodic_report.py --period weekly` 可生成周报；
- `python scripts/generate_periodic_report.py --period monthly` 可生成月度财务包；
- `python scripts/generate_periodic_report.py --period quarterly` 可生成季度报税数据包；
- 邮件能收到附件；
- Excel 摘要页能清楚显示运营快报和稳定盈亏；
- 季度数据包能显示版本、状态、原始报告索引和会计复核提示；
- 报表日志记录成功/失败状态。

### Phase 5：Azure 部署与定时运行

目标：系统在 Azure 上自动运行。

任务：

1. 编写 GitHub Actions deploy workflow；
2. 构建 Docker 镜像并推送到 ACR；
3. 创建 Submit Report Requests Job；
4. 创建 Collect Ready Reports Job；
5. 创建 Periodic Report Job；
6. 配置 cron；
6. 配置 Job Managed Identity；
7. 配置 Key Vault 权限；
8. 配置日志查询；
9. 手动触发测试；
10. 等待定时任务自动执行验证。

验收：

- GitHub push 后可自动构建镜像；
- Container Apps Job 使用新镜像；
- Submit Job 能自动提交 Amazon 报表请求；
- Collect Job 能自动下载并解析已完成报表；
- Periodic Report Job 能自动发周报/月报/季度数据包；
- Azure 日志可查；
- SQL run log 可查。

### Phase 6：对账与优化

目标：提高可信度并降低长期维护成本。

任务：

1. 将系统周报与 Seller Central 手动下载报表对账；
2. 对 Ads spend 与 Payments 广告扣费对账；
3. 对月度利润与会计口径对账；
4. 优化费用分类规则；
5. 补充异常提醒；
6. 增加历史趋势 Sheet；
7. 增加 SKU 库存周转预测。

验收：

- 连续 4 周报表可稳定生成；
- 周度结果与人工核算差异可解释；
- 主要费用分类准确；
- 可用于每周运营决策。

---

## 16. 验收标准

第一版上线可用标准：

```text
1. 每天自动提交最近45天所需 Amazon 报表请求。
2. 每30~60分钟自动检查并下载已完成报告。
3. 已下载原始报告能归档到 Azure Blob Storage。
4. 销售、广告、财务、库存、促销数据能标准化入库。
5. 每周一自动生成 Excel 周报并发送到邮箱。
6. Excel 中同时包含最近完整周运营快报和上上完整周稳定盈亏。
7. 周报明确展示总收入、总支出、广告费、促销费、Amazon费用、采购成本、头程成本、估算利润。
8. 重复执行同步任务不会导致重复计算。
9. 缺失数据会在报表中提示。
10. 所有密钥不进入 GitHub 代码仓库。
11. Azure SQL 中有完整运行日志、报告请求状态和报表发送日志。
12. 至少抽样核对 1 个完整周的数据，与 Seller Central 手工报表基本一致。
13. 能手动生成一个月度财务包初版。
14. 能手动生成一个季度报税数据包初版，并显示“会计复核/非最终申报”提示。
```

---

## 17. 需要提前确认的问题

开发前需要确认以下信息：

1. Amazon 店铺 marketplace：美国站为主，是否后续扩展英国/欧洲站；
2. 当前 Sponsored Products 是否只有一个 Ads profile；
3. 店铺 SKU 成本数据是否完整，包括采购、头程、包装；
4. 是否已有 SP-API app 和 refresh token；
5. 是否已有 Ads API 权限和 refresh token；
6. 报表收件邮箱；
7. 邮件发送方式：SMTP 还是 Microsoft Graph；
8. Azure SQL 是否已创建免费数据库；
9. 是否允许 Azure SQL 超出免费额度后继续付费，还是达到免费额度自动暂停；
10. 周报币种是否统一使用 GBP/USD，是否需要汇率换算为 RMB；
11. 季度报税数据包主要服务于中国公司账务、英国个人/公司账务，还是美国相关申报；
12. 会计希望季度包按自然季度还是公司财务年度季度；
13. 季度包是否需要导出原始交易明细，还是只要分类汇总；
14. 是否需要把采购发票、物流发票、银行流水等非 Amazon 数据也纳入后续系统。

---

## 18. 当前推荐的第一批实现范围

为了避免一开始过度复杂，第一批只做这些：

```text
P0：报告请求状态表
P0：提交报告请求 Job
P0：检查/下载/解析完成报告 Job
P0：销售数据同步
P0：财务事件同步
P0：Sponsored Products 广告数据同步
P0：SKU 成本表
P0：库存快照
P0：周利润计算
P0：Excel 邮件周报
P0：Azure Blob 原始报表归档
P0：Azure Container Apps Job 部署
```

暂缓：

```text
P1：月度财务包自动生成
P1：季度报税数据包自动生成
P1：季度锁账/版本机制
P1：复杂促销报表精细化
P1：多 marketplace 支持
P1：网页看板
P1：自动广告调价建议
P1：汇率自动换算
P1：图表趋势页
```

---

## 19. 风险与控制措施

| 风险 | 影响 | 控制措施 |
|---|---|---|
| Amazon API 权限申请/授权复杂 | 影响开发启动 | 先完成 token 测试脚本 |
| 报表字段变化 | 解析失败 | 解析器允许未知字段，保留 raw_data |
| 数据延迟 | 周报不准 | 每天回刷 45 天，稳定盈亏延迟一周 |
| 广告费重复扣除 | 利润偏低 | 周报广告费统一用 Ads API spend，Payments 广告账单只对账 |
| SKU 成本缺失 | 利润不准 | Excel 明确提示缺失 SKU，不计算假利润 |
| Azure SQL 免费额度耗尽 | 同步失败或产生费用 | 监控 vCore 使用量，表做索引，避免频繁大查询 |
| Key Vault 权限错误 | Job 无法读取密钥 | Managed Identity 权限测试纳入验收 |
| Job 超时 | 同步不完整 | 拆成提交/采集/报表三个 Job，不长时间等待报告 |
| 报表长时间未生成 | 数据延迟 | `collect_ready_reports` 定时检查，超过阈值后报警或标记异常 |
| 季度报表被回刷覆盖 | 报税版本不可追溯 | 月报/季报使用 draft/stable/locked/amended 版本机制 |
| 原始报表缺失 | 会计或审计无法追溯 | 原始下载文件和生成报表归档到 Azure Blob Storage |

---

## 20. 参考资料

1. Azure Container Apps Jobs 官方文档：说明 Jobs 是有限时长运行并停止的容器化任务，支持 Manual、Schedule、Event 触发；Scheduled Job 使用 5 字段 cron，且按 UTC 计算。  
   https://learn.microsoft.com/en-us/azure/container-apps/jobs

2. Azure Container Apps Billing 官方文档：Consumption plan 下 Jobs 按执行期间资源收费，任务完成后不产生 idle charges。  
   https://learn.microsoft.com/en-us/azure/container-apps/billing

3. Azure Container Apps Pricing 官方页面：Consumption plan 每月包含一定免费 vCPU-seconds、GiB-seconds 和 requests。  
   https://azure.microsoft.com/en-us/pricing/details/container-apps/

4. Azure Key Vault Authentication 官方文档：Azure 资源可通过 Managed Identity 获取 token 并访问 Key Vault。  
   https://learn.microsoft.com/en-us/azure/key-vault/general/authentication

5. Azure SQL Database Free Offer 官方文档：每个免费数据库每月包含 100,000 vCore seconds、32GB data、32GB backup storage。  
   https://learn.microsoft.com/en-us/azure/azure-sql/database/free-offer

6. Amazon SP-API Reports API 官方文档：Reports API 用于获取和管理可帮助卖家经营的报表，可用于库存、履约订单、税务、退货等。  
   https://developer-docs.amazon.com/sp-api/docs/reports-api

7. Amazon SP-API createReport 官方文档：创建报表需要 reportType、dataStartTime、dataEndTime、marketplaceIds 等参数。  
   https://developer-docs.amazon.com/sp-api/reference/createreport

8. Amazon SP-API Finances API 官方文档：Finances API 可按订单或日期范围获取卖家相关财务事件，无需等待结算周期关闭。  
   https://developer-docs.amazon.com/sp-api/docs/finances-api

9. Amazon Ads API Reporting v3 官方文档：广告报表支持按 campaign、ad group、ad、keyword、target 等维度获取表现数据。  
   https://advertising.amazon.com/API/docs/en-us/guides/reporting/v3/overview

---

## 21. 总结

本系统的核心不是做一个复杂后台，而是建立一个稳定、低成本、可持续扩展的数据管道：

```text
每天自动提交和采集 Amazon 报告
每周自动生成周报
每月生成财务包
每季度生成报税数据包
利润口径明确
数据延迟有处理
费用分类可追溯
原始报表可归档追溯
结果可人工核验与锁账
```

最终推荐架构为：

```text
Azure Container Apps Job 负责执行
Azure SQL 负责存储和任务状态
Azure Blob Storage 负责原始文件和报表归档
Azure Key Vault 负责密钥
GitHub Actions 负责部署
Excel 邮件负责交付
```

这套方案适合当前小体量店铺，也为以后扩展到更多站点、更多产品、月度财务包、季度报税数据包、网页看板、自动广告优化打好基础。
