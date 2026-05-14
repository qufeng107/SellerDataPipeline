# SellerDataPipeline

SellerDataPipeline 是一个轻量级的跨境电商运营数据管道项目。第一阶段聚焦 **Amazon Seller Central / Amazon Ads** 数据自动化，用于定期同步销售、财务、广告、库存等数据到 Azure SQL，并生成周报、月报和季度报税数据包。

当前项目定位：

- 不做 Django / Web 后台。
- 使用普通 Python 脚本组织业务逻辑。
- 使用 Docker 镜像部署到 Azure Container Apps Job。
- 使用 Azure SQL 保存结构化经营数据。
- 使用 Azure Key Vault 保存 API 密钥、数据库密码、邮箱凭证等敏感信息。
- 使用 Azure Blob Storage 归档原始报告和生成后的 Excel 报表。
- 使用 GitHub Actions 做测试、构建镜像和部署，不把 GitHub Actions 当作长期业务定时器。

---

## 一、核心业务流程

系统按三类 Job 运行，三类 Job 共用同一个 Docker 镜像，只是启动命令不同。

### 1. 提交 Amazon 报告请求

入口：

```bash
python scripts/submit_report_requests.py --days 45
```

职责：

- 计算需要请求的数据时间范围。
- 调用 Amazon SP-API Reports API 的 `createReport`。
- 将 `report_id`、`report_type`、时间范围、marketplace、状态写入 `amazon_report_request` 表。
- 不在该任务中长时间等待报告生成。

### 2. 收集已完成报告

入口：

```bash
python scripts/collect_ready_reports.py --limit 20
```

职责：

- 从数据库读取未完成的 report request。
- 调用 Amazon `getReport` 查询状态。
- 对 `DONE` 报告调用 `getReportDocument` 下载文件。
- 解析报告并 upsert 到 Azure SQL。
- 更新报告请求状态。

### 3. 生成周期报表

入口：

```bash
python scripts/generate_periodic_reports.py --type weekly
python scripts/generate_periodic_reports.py --type monthly
python scripts/generate_periodic_reports.py --type quarterly
```

职责：

- 从 Azure SQL 读取已入库数据。
- 生成最近完整周运营快报。
- 生成上上完整周稳定盈亏报。
- 生成月度财务包。
- 生成季度报税数据包。
- 生成 Excel，上传 Blob Storage，并发送邮件。

---

## 二、目录结构规范

项目采用 `src/ + scripts/ + tests/` 结构：

```text
SellerDataPipeline/
  README.md
  Dockerfile
  requirements.txt
  pyproject.toml
  .env.example

  sql/
    migrations/                 # Azure SQL 建表与索引脚本
    seeds/                      # 示例基础数据，例如 SKU 成本样例

  src/
    seller_data_pipeline/
      config/                   # 配置读取：环境变量、运行环境、默认参数
      common/                   # 公共工具：日志、日期窗口、金额处理、异常、重试
      integrations/
        amazon/                 # Amazon SP-API / Ads API 客户端和报告下载逻辑
      db/                       # Azure SQL 连接、SQL 执行、Repository 层
      parsers/
        amazon/                 # Amazon 原始报告解析器
      services/                 # 业务服务层：提交请求、收集报告、利润计算、邮件发送
      reports/                  # Excel 报表构建器：周报、月报、季报
      jobs/                     # 三类 Container Apps Job 的业务入口

  scripts/                      # 命令行入口；只做参数解析和调用 jobs，不写复杂业务
  tests/                        # 测试代码
    unit/                       # 单元测试，不依赖真实 Azure / Amazon
    integration/                # 集成测试，需要真实环境变量和外部服务
    fixtures/                   # 测试样本数据

  .github/workflows/            # CI 和后续部署 workflow
```

### 重要约定

1. `scripts/` 只放很薄的命令行入口，不写复杂业务逻辑。
2. 真正业务逻辑放在 `src/seller_data_pipeline/services/`。
3. Amazon API 相关代码统一放在 `src/seller_data_pipeline/integrations/amazon/`。
4. 报告解析逻辑统一放在 `src/seller_data_pipeline/parsers/amazon/`。
5. 数据库读写统一通过 `src/seller_data_pipeline/db/repositories/`，不要在业务代码中到处拼 SQL。
6. Excel 生成统一放在 `src/seller_data_pipeline/reports/`。
7. 单元测试按源码模块镜像组织，优先测试 parser、日期窗口、利润计算、报表生成。

---

## 三、开发环境

建议使用 Python 3.11。

安装依赖：

```bash
pip install -r requirements.txt
```

本地开发时复制环境变量模板：

```bash
cp .env.example .env
```

`.env` 不允许提交到 GitHub。

运行单元测试：

```bash
pytest tests/unit
```

执行代码检查：

```bash
ruff check src tests
ruff format src tests
```

---

## 四、常用命令

提交报告请求：

```bash
python scripts/submit_report_requests.py --days 45
```

收集已完成报告：

```bash
python scripts/collect_ready_reports.py --limit 20
```


### 本地 Sampling Mode：分析已下载报告字段

下载 raw report 后，可以先不入库，而是生成脱敏字段取样文档：

```bash
PYTHONPATH=src python scripts/analyze_raw_report.py \
  --raw-file reports/raw/amazon/ATVPDKIKX0DER/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA/2026-05-14/112429020587.txt \
  --report-type GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA \
  --marketplace-id ATVPDKIKX0DER \
  --output-md requirements/data_samples/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA.md
```

销售与流量报告是 JSON 格式，也可以用同一个 analyzer 自动识别：

```bash
PYTHONPATH=src python scripts/analyze_raw_report.py \
  --raw-file reports/raw/amazon/ATVPDKIKX0DER/GET_SALES_AND_TRAFFIC_REPORT/2026-05-14/112441020587.txt \
  --report-type GET_SALES_AND_TRAFFIC_REPORT \
  --marketplace-id ATVPDKIKX0DER \
  --output-md requirements/data_samples/GET_SALES_AND_TRAFFIC_REPORT.md
```


### 本地 Sampling Mode：发现自动生成的 Settlement 报告

Settlement reports 不能通过 `createReport` 主动请求，需要先用 `getReports` 发现 Amazon 自动生成的 DONE 报告：

```bash
PYTHONPATH=src python scripts/discover_available_reports.py   --report-type GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2   --days 89
```

如果发现 report，会生成本地 request manifest：

```text
runtime/sampling/report_requests/{report_id}.json
```

然后复用已有下载脚本：

```bash
PYTHONPATH=src python scripts/collect_ready_reports.py --limit 10
```

下载成功后，Settlement 建议用聚合 analyzer 一次分析同一天下载的多份 report：

```bash
PYTHONPATH=src python scripts/analyze_settlement_reports.py \
  --raw-dir reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/{date} \
  --marketplace-id ATVPDKIKX0DER \
  --output-md requirements/data_samples/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.md
```

这个脚本会统计 `transaction-type`、`amount-type`、`amount-description`，并基于 parser 的第一版 `amount_category` / `profit_bucket` 输出费用分类分布。

注意：`reports/raw/` 和 `runtime/` 可能包含真实经营数据，只保留在本地，不提交 GitHub。

### 本地 Sampling Mode：Amazon Ads API 取样

Amazon Ads API 使用独立的 Ads refresh token 和 profile ID。先在 `.env` 中配置：

```bash
AMAZON_ADS_REFRESH_TOKEN='...'
AMAZON_ADS_PROFILE_ID='...'
```

如果暂时不知道 profile ID，先运行：

```bash
PYTHONPATH=src python scripts/discover_ads_profiles.py
```

发现 profile 后，可以 dry-run 查看默认 Sponsored Products 取样计划：

```bash
PYTHONPATH=src python scripts/run_ads_sampling_plan.py --dry-run
```

第一批 Ads 取样默认覆盖：

```text
spCampaigns
spTargeting
spSearchTerm
spAdvertisedProduct
spPurchasedProduct
```

提交 Ads 报告请求：

```bash
PYTHONPATH=src python scripts/run_ads_sampling_plan.py
```

轮询并下载已完成 Ads 报告：

```bash
PYTHONPATH=src python scripts/collect_ads_reports.py --limit 20
```

下载后的原始文件会保存到：

```text
reports/raw/amazon_ads/{profile_id}/{report_type_id}/{date}/{ads_report_id}.json
```

Ads API 当前仍处于取样阶段：先拿真实 raw report，再根据字段样例补 parser 和 `database_spec.md`。


生成周报：

```bash
python scripts/generate_periodic_reports.py --type weekly
```

生成月报：

```bash
python scripts/generate_periodic_reports.py --type monthly
```

生成季度报税数据包：

```bash
python scripts/generate_periodic_reports.py --type quarterly
```

---

## 五、部署设计

最终部署方式：

```text
GitHub Repository
  ↓
GitHub Actions: 测试、构建 Docker 镜像
  ↓
Azure Container Registry
  ↓
Azure Container Apps Job
  ↓
Azure SQL / Key Vault / Blob Storage
```

Azure 上建议配置三个 Container Apps Job：

| Job | 建议命令 | 频率 |
|---|---|---|
| submit-report-requests | `python scripts/submit_report_requests.py --days 45` | 每天 1 次 |
| collect-ready-reports | `python scripts/collect_ready_reports.py --limit 20` | 每 30-60 分钟 |
| generate-periodic-reports | `python scripts/generate_periodic_reports.py --type weekly` | 每周一 |

月报和季报可以复用第三个 Job，使用不同命令或不同计划触发。

---

## 六、数据口径原则

### 周报

- 运营快报：最近完整自然周，主要用于看销量、广告、库存和运营动作。
- 稳定盈亏：上上个完整自然周，主要用于判断更接近真实的盈亏。
- Sponsored Products 商品广告按 Seller 常见 7 天归因窗口设计，因此利润判断需要延迟复核。

### 月报 / 季报

- 月报用于会计复核和正式财务整理。
- 季报定位为“季度报税数据包”，不直接替代最终税务申报。
- 季报需要支持版本状态：`draft / stable / locked / amended`。
- 锁账后不得自动覆盖，只能生成修正版。

---

## 七、安全规范

禁止提交任何真实密钥，包括：

- Amazon LWA Client ID / Client Secret
- Amazon SP-API Refresh Token
- Amazon Ads Refresh Token
- Azure SQL 密码
- SMTP 邮箱密码
- Azure Storage 连接字符串

本地使用 `.env`，云上使用 Azure Key Vault。

---

## 八、当前骨架状态

当前提交的是项目初始骨架，主要用于统一未来开发规范。大多数服务类是占位实现，后续开发时按以下顺序推进：

1. 完善 Azure SQL 建表脚本。
2. 实现配置读取和日志。
3. 实现日期窗口、金额处理、upsert 基础工具。
4. 实现 Amazon SP-API 鉴权和 Reports API 流程。
5. 实现报告解析器。
6. 实现三类 Job。
7. 实现 Excel 周报/月报/季报。
8. 接入 Docker、Azure Container Apps Job 和 GitHub Actions 部署。

---

## 九、当前开发阶段：SP-API 连通性测试

在已经创建 SP-API Production Private Application，并完成 self-authorization 后，先不要直接开发完整报表流程。当前第一步目标是验证本地凭证能成功调用 SP-API。

### 1. 配置本地 `.env`

复制模板：

```bash
cp .env.example .env
```

在 `.env` 中填入你从 Amazon Solution Provider Portal 获取的三个核心值：

```env
AMAZON_REGION=NA
AMAZON_MARKETPLACE_ID=ATVPDKIKX0DER
AMAZON_SP_API_ENDPOINT=https://sellingpartnerapi-na.amazon.com
AMAZON_LWA_TOKEN_URL=https://api.amazon.com/auth/o2/token
AMAZON_SP_API_USER_AGENT=SellerDataPipeline/0.1.0 (Language=Python/3.11)

AMAZON_LWA_CLIENT_ID=your_lwa_client_id
AMAZON_LWA_CLIENT_SECRET=your_lwa_client_secret
AMAZON_SP_API_REFRESH_TOKEN=your_refresh_token
```

`.env` 只用于本地开发，不能提交到 GitHub。

### 2. 运行 SP-API 连接测试

```bash
python scripts/test_sp_api_connection.py
```

成功后会输出类似：

```text
SP-API connection test succeeded.
Marketplace participations:
- ATVPDKIKX0DER | Amazon.com | US | USD
```

需要查看原始响应时可加：

```bash
python scripts/test_sp_api_connection.py --show-raw
```

### 3. 当前验收标准

这一阶段只验证认证链路和基础访问权限：

1. 能用 refresh token 换取 LWA access token。
2. 能调用 `GET /sellers/v1/marketplaceParticipations`。
3. 能看到授权账号参与的 marketplace 信息。
4. 不在日志或 GitHub 中输出任何 client secret、refresh token 或 access token。

通过后再进入下一步：实现 Reports API 的 `createReport -> getReport -> getReportDocument -> download -> parse` 异步流程。

---

## 十、当前开发阶段：Local Sampling Mode + Reports API 最小闭环

数据库目前尚未建表。为了避免一开始把业务表字段设计死，当前阶段采用本地 Sampling Mode：先请求真实 Amazon report，下载原始文件，生成本地 manifest，再根据真实字段更新 `requirements/database_spec.md`。

### 1. 提交第一份 Listing report 请求

`GET_MERCHANT_LISTINGS_ALL_DATA` 默认不传日期窗口：

```bash
PYTHONPATH=src python scripts/submit_report_requests.py \
  --report-type GET_MERCHANT_LISTINGS_ALL_DATA
```

成功后会生成：

```text
runtime/sampling/report_requests/{report_id}.json
```

### 2. 轮询并下载已完成报告

Amazon report 是异步生成的，可能需要隔几分钟重复运行：

```bash
PYTHONPATH=src python scripts/collect_ready_reports.py --limit 10
```

如果状态变为 `DONE`，会下载到：

```text
reports/raw/amazon/{marketplace_id}/{report_type}/{date}/{report_id}.txt
runtime/sampling/raw_files/{report_id}.json
```

raw file manifest 会保存：

```text
checksum_sha256
size_bytes
encoding
delimiter
header
sample_rows
```

### 3. 带日期窗口的报告

某些 report type 需要日期窗口，可以传 `--days`：

```bash
PYTHONPATH=src python scripts/submit_report_requests.py \
  --report-type GET_SALES_AND_TRAFFIC_REPORT \
  --days 7
```

### 4. 安全注意

`runtime/` 和 `reports/raw/` 已被 `.gitignore` 忽略，里面可能包含真实经营数据，不得提交 GitHub。

### 5. 分析已下载 raw report 字段结构

下载成功后，先不要急着入库。应先用 analyzer 生成脱敏字段取样文档：

```bash
PYTHONPATH=src python scripts/analyze_raw_report.py \
  --raw-file reports/raw/amazon/ATVPDKIKX0DER/GET_MERCHANT_LISTINGS_ALL_DATA/2026-05-13/112285020586.txt \
  --report-type GET_MERCHANT_LISTINGS_ALL_DATA \
  --marketplace-id ATVPDKIKX0DER \
  --output-md requirements/data_samples/GET_MERCHANT_LISTINGS_ALL_DATA.md
```

默认会脱敏 SKU、ASIN、Listing ID、产品标题、描述等样例值，适合提交到仓库。不要使用 `--show-raw-sample-values` 生成要提交的文档。

### 6. 当前 Listing parser

已新增：

```text
src/seller_data_pipeline/parsers/amazon/listings_all_data_parser.py
```

它会把 `GET_MERCHANT_LISTINGS_ALL_DATA` 转为内存中的 Listing snapshot records，但当前不写数据库。等 `requirements/database_spec.md` 里的 `amazon_listing_snapshot` 从 `sampling` 升级为 `confirmed` 后，再实现 repository 和 SQL upsert。

### 7. 当前已验证的取样报告

截至 2026-05-14，已完成本地取样并进入 database spec 的报告包括：

| report_type | file_format | 当前结论 |
|---|---|---|
| `GET_MERCHANT_LISTINGS_ALL_DATA` | tab-delimited flat file | 可用于 `amazon_listing_snapshot`，但不作为 FBA 库存主来源 |
| `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | tab-delimited flat file | 可用于 `amazon_inventory_daily`，主库存口径暂定 `afn-fulfillable-quantity` |
| `GET_SALES_AND_TRAFFIC_REPORT` | JSON | 可用于 `amazon_sales_traffic_daily` 和 PARENT ASIN 粒度的 `amazon_sales_traffic_asin_daily` |
| `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | tab-delimited flat file | 已下载 8 份，支持 `amazon_settlement_transaction` 和费用分类草案 |

当前仍不建议执行 SQL 建表。下一步应优先取样财务费用侧数据，用来确认 Amazon fee、FBA fee、退款金额、赔偿、清算、月租、促销/Coupon 成本等字段。


### 8. 批量取样更多 Amazon Reports

当前阶段建议先尽量下载可用 raw 样例，再更新字段样例、parser 和 database spec。

查看批量取样计划，不调用 Amazon：

```bash
PYTHONPATH=src python scripts/run_sampling_plan.py --dry-run
```

执行默认非敏感取样计划：

```bash
PYTHONPATH=src python scripts/run_sampling_plan.py
```

然后下载已完成报告：

```bash
PYTHONPATH=src python scripts/collect_ready_reports.py --limit 50
```

默认计划会跳过可能包含客户 PII/客户评论的高敏报告。如确实需要完整取样，再显式使用：

```bash
PYTHONPATH=src python scripts/run_sampling_plan.py --include-sensitive
```

批量计划文档见：

```text
requirements/amazon_report_sampling_plan.md
```

### Batch sampling v1.0 notes

After the first batch sampling run, these additional report families are now supported by field docs and parser drafts:

```text
GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL
GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE
GET_FBA_REIMBURSEMENTS_DATA
GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA
GET_FBA_INVENTORY_PLANNING_DATA
GET_LEDGER_SUMMARY_VIEW_DATA
```

The sampling plan no longer sends an explicit empty `eventType` for `GET_LEDGER_DETAIL_VIEW_DATA`, because the current SP-API validation rejected an empty string value. Retry it without report options first.

Continue the sampling stage before creating Azure SQL tables:

```powershell
python scripts/collect_ready_reports.py --limit 50
python scripts/run_sampling_plan.py --dry-run
python scripts/run_sampling_plan.py
python scripts/collect_ready_reports.py --limit 50
```

### Batch sampling v1.1 notes

Second batch sampling added parser/spec coverage for:

```text
GET_LEDGER_DETAIL_VIEW_DATA
GET_RESERVED_INVENTORY_DATA
GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT
```

`collect_ready_reports.py` now also downloads diagnostic documents for `FATAL` reports when Amazon returns a `reportDocumentId`. These files are stored with `download_status=DIAGNOSTIC_DOWNLOADED` and should be used for troubleshooting only, not as business data.

Run:

```powershell
python scripts/collect_ready_reports.py --limit 50
```

to fetch diagnostic documents for failed Coupon/Promotion reports if Amazon provides them.

### Promotion / Coupon performance report options

`GET_PROMOTION_PERFORMANCE_REPORT` and `GET_COUPON_PERFORMANCE_REPORT` require report-specific date options. The batch sampling plan now supplies these automatically:

```text
promotionStartDateFrom / promotionStartDateTo
couponStartDateFrom / couponStartDateTo
```

To retry only these reports after applying the update:

```powershell
python scripts/run_sampling_plan.py --only-report-type GET_PROMOTION_PERFORMANCE_REPORT
python scripts/run_sampling_plan.py --only-report-type GET_COUPON_PERFORMANCE_REPORT
python scripts/collect_ready_reports.py --limit 50
```

### Promotion / Coupon sampling v1.3

After adding report-specific date options, both performance reports can be sampled successfully:

```powershell
python scripts/run_sampling_plan.py --only-report-type GET_PROMOTION_PERFORMANCE_REPORT
python scripts/run_sampling_plan.py --only-report-type GET_COUPON_PERFORMANCE_REPORT
python scripts/collect_ready_reports.py --limit 50
```

New parsers:

```text
src/seller_data_pipeline/parsers/amazon/promotion_coupon_parser.py
```

The parser splits nested JSON into separate records:

```text
Promotion: promotion-level records + includedProducts ASIN records
Coupon: coupon-level records + coupon-ASIN records
```

These reports are operational performance sources. Settlement V2 remains the primary financial source for actual promotion/coupon costs in profit calculations.
