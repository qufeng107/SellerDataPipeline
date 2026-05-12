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
