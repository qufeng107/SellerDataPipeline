# SellerDataPipeline 当前进展与下一步计划

> 更新时间：2026-05-15  
> 当前更新：v1.13 Amazon Ads 入库前 dry-run 守门链路已完成；本轮 chat 已完成 Ads 取样收口与下一阶段入库/审计/通知规划；Azure 参数尚未配置，SQL 仍未执行。  
> 文档用途：记录项目真实进展、阶段结论、后续计划和注意事项。长期架构以 `requirements/amazon_profit_report_serverless_design_plan_v1_1.md` 为参考；数据库唯一事实以 `requirements/database_spec.md` 为准；本文件负责说明“现在做到哪里、下一步做什么”。

---

## 1. 当前一句话状态

当前项目已经完成 **Amazon SP-API Reports 本地取样主流程**：

```text
SP-API 授权/连接测试
  -> Local Sampling Mode
  -> createReport / getReports discovery
  -> getReport / getReportDocument
  -> 下载 raw reports
  -> 生成本地 manifest
  -> 生成脱敏字段样例文档
  -> 编写第一批 parser 草案
  -> 根据真实样例持续更新 database_spec.md
```

数据库 **Azure SQL 已开通但尚未建表**。当前策略保持不变：

```text
先 raw，后 normalized。
先样例，后字段。
先 spec，后 SQL。
先采集闭环，后分析报表。
控制表先稳定，业务表边取样边确认。
```

Amazon Ads API 已经开通，用户已取得 Ads API 相关环境变量。当前主线临时从 SQL 执行切回 Ads：只读连接自检、profile 选择、`spCampaigns`、`spTargeting`、`spSearchTerm`、`spAdvertisedProduct` 四个 3 天 canary 均已完成并下载 raw JSON，已生成脱敏字段样例。SQL 执行继续搁置。

本轮 v1.13 已完成：

```text
Amazon Ads US profile=3917953989967300 已确认 valid_payment=true
spCampaigns / spTargeting / spSearchTerm / spAdvertisedProduct 四个核心 Ads canary 均已完成
spPurchasedProduct API 已接受且下载成功，但当前 3 天窗口为空，暂不建表
schema validation 已覆盖 Ads 已下载 raw reports，四个核心报表均为 ok
新增 prepare_ads_ingestion.py，可把已下载 Ads raw 转成 DB-ready preview JSONL
新增 ingestion/ads_table_mapping.py，集中管理 Ads 目标表、字段、业务唯一键和 business_key_hash
新增 ingestion/ads_ingestion_dry_run.py，生成 ads_ingestion_summary.json、task_audit_event.json、schema_validation_events.jsonl
SQL migration 草案已为 Ads 四张核心表补充 business_key_hash 和唯一索引，但仍不执行 Azure SQL
下一步建议：审查 dry-run preview；然后执行 Azure SQL 建表；再实现真实 repository/upsert 与邮件通知
```

---


## 1.1 本轮 Chat 收口摘要：Ads 取样与入库前守门链路

> 记录日期：2026-05-15  
> 目的：给下一次 chat / 下一阶段开发做 handoff，避免忘记本轮关键决策、真实验证结果和注意事项。

### A. 本轮已经确认的事实

1. **Azure SQL 执行继续搁置**：用户明确表示 Azure 参数尚未配置，真实建表与真实入库将在新 chat 继续。
2. **Amazon Ads API 已开通并可用**：`scripts/test_ads_api_connection.py` 已成功获取 LWA access token，并发现 4 个 profiles。
3. **US 广告 profile 已确认**：

```text
profile_id = 3917953989967300
country = US
currency = USD
timezone = America/Los_Angeles
account_type = seller
account_name = Cuide market
valid_payment = True
```

4. BR profile `909721457096469` 的 `valid_payment=False`，不作为当前 US 店铺广告数据主线。
5. PowerShell 中不要使用 Bash 风格 `\` 换行；需要用单行命令或 PowerShell 反引号续行。
6. `Get-Content` 在 Windows PowerShell 下查看 UTF-8 JSONL 时可能显示中文乱码；这通常是控制台编码显示问题，不代表 raw file 或 Python 解析坏了。需要用 VS Code、Python、或 `Get-Content -Encoding utf8` 查看。

### B. Amazon Ads 实测 canary 结果

| reportTypeId | report_id | 取样窗口 | 下载状态 | normalized_rows | schema 状态 | 当前结论 |
|---|---|---|---|---:|---|---|
| `spCampaigns` | `5dc8e80b-72cc-4e37-864f-e877b7f90e5c` | 2026-05-12 至 2026-05-15 | DOWNLOADED | 8 | ok | 第一批入库 |
| `spTargeting` | `c89e0e82-be20-468d-8ec7-884a1d623e9f` | 2026-05-12 至 2026-05-15 | DOWNLOADED | 99 | ok | 第一批入库 |
| `spSearchTerm` | `4c38fa3c-8595-40c3-8e9f-2c52e90641a9` | 2026-05-12 至 2026-05-15 | DOWNLOADED | 61 | ok | 第一批入库 |
| `spAdvertisedProduct` | `b6754b6b-482b-4169-8fe3-86e0af5065b3` | 2026-05-12 至 2026-05-15 | DOWNLOADED | 32 | ok | 第一批入库 |
| `spPurchasedProduct` | `7ee85e28-5800-4095-8f7f-d111e70445c1` | 2026-05-12 至 2026-05-15 | DOWNLOADED | 0 | empty_report | API 可用但当前窗口为空，暂不建表 |

第一批 Ads 入库表只包含 4 张非空 confirmed 表：

```text
amazon_ads_sp_campaign_daily
amazon_ads_sp_targeting_daily
amazon_ads_sp_search_term_daily
amazon_ads_sp_advertised_product_daily
```

`amazon_ads_sp_purchased_product_daily` 暂缓，等未来用 14/30 天窗口拿到非空样例后再进入 database spec 和 migration。

### C. 当前已实现的 Ads 入库前守门能力

当前代码已具备以下能力：

```text
Ads raw file 下载与本地留存
  -> 脱敏字段样例 ADS_*.md
  -> schema validation / schema drift 检测
  -> parser normalized rows
  -> prepare_ads_ingestion.py 生成 DB-ready preview JSONL
  -> 生成 ads_ingestion_summary.json
  -> 生成 task_audit_event.json
  -> 生成 schema_validation_events.jsonl
```

用户本地已验证：

```text
python scripts/prepare_ads_ingestion.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER

Ads ingestion dry-run status=success
processed_files=4
parsed_rows=200
prepared_rows=200
preview_files=4
requires_review=False
```

当前 zip 实际代码状态：

```text
已实现：scripts/prepare_ads_ingestion.py
已实现：src/seller_data_pipeline/ingestion/ads_table_mapping.py
已实现：src/seller_data_pipeline/ingestion/ads_ingestion_dry_run.py
已实现：src/seller_data_pipeline/sampling/schema_drift.py
尚未完成：真实 Ads repository/upsert
尚未完成：scripts/ingest_ads_reports.py 正式入库入口
尚未完成：邮件通知 notifier
尚未完成：Azure Container Apps Jobs 自动任务
```

注意：`src/seller_data_pipeline/db/repositories/ads_repo.py` 当前仍是 placeholder，不要误认为真实 Ads 入库已实现。

### D. 长期数据库稳定维护原则

本轮明确以下长期规则，后续必须继续遵守：

1. **raw file 必须留存**：Amazon 下载的 raw report 是事实源，不因 parser 或表结构变化而丢弃。
2. **入库前必须 schema validation**：不能等 SQL 报错才发现字段变化。
3. **字段漂移必须阻断入库**：`new_fields`、`missing_fields`、`schema_drift`、`unmapped_fields`、`validation_failed` 默认 `requires_review=true`。
4. **需要人工检查时后续要邮件通知**：入库失败、字段漂移、API 失败达到重试上限、异常空报表等，都要触发通知。
5. **`database_spec.md` 是数据库唯一事实文档**：任何字段、表、业务唯一键变化，必须先改 spec，再改 SQL migration，再改 parser/mapping/repository/tests。
6. **已执行 migration 不可修改**：SQL 在 Azure 执行之前可以重写 001/002；一旦执行，只能新增 003/004 迁移。
7. **业务键和 raw 追溯键分离**：

```text
business_key_hash = 未来 upsert 的稳定业务唯一键
source_row_hash   = raw row 追溯与审计
```

### E. 下一阶段推荐顺序

下一次 chat 建议从以下顺序继续：

```text
1. 配置 Azure SQL .env 参数
2. 运行 scripts/test_azure_sql_connection.py --json
3. dry-run SQL migration：001_create_core_tables.sql / 002_create_indexes.sql
4. 人工确认 SQL 表结构与 database_spec.md 一致
5. 执行 001/002 建表
6. 实现真实 AdsRepo upsert，白名单限制只能写 Ads 四张表和审计表
7. 新增 scripts/ingest_ads_reports.py，默认 dry-run，显式 --execute 才写库
8. 写入 amazon_sync_run_log 任务审计
9. 写入 amazon_schema_validation_event 字段漂移事件
10. 增加 email notifier，出现 requires_review 或入库失败时通知用户
11. 最后再接 Azure Container Apps Jobs 自动任务
```


## 2. 项目目标简述

SellerDataPipeline 是一个用于亚马逊卖家运营与财务数据自动化的轻量级数据管道项目。

长期目标：

1. 自动从 Amazon SP-API 和 Amazon Ads API 获取销售、财务、库存、广告、Listing、促销、优惠券等数据。
2. 保存 Amazon 原始 report 文件，保留可追溯证据。
3. 将标准化后的运营与财务数据写入 Azure SQL Database。
4. 基于数据库生成：
   - 每周运营快报
   - 上上完整周稳定盈亏报
   - 月度财务包
   - 季度会计/报税准备数据包
5. 后续通过 Azure Container Apps Job 定时运行，并生成 Excel 文件，可进一步接入邮件发送。

当前项目暂不做 Django 后台，也暂不做实时网页看板。第一阶段重点是把数据源取样、字段确认、数据库设计和后续报表生成链路打通。

---

## 3. 已完成基础事项

### 3.1 项目骨架与代码规范

已建立项目结构：

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

目录约定：

1. `src/seller_data_pipeline/` 存放核心业务逻辑。
2. `scripts/` 存放本地和云端 Job 的薄入口脚本。
3. `tests/` 存放单元测试和后续集成测试。
4. `sql/migrations/` 存放数据库建表和结构变更脚本。
5. `requirements/` 存放设计、进度、数据样例和取样计划文档。
6. `.env.example` 只保留环境变量示例，不存放真实密钥。
7. `.env` 仅用于本地开发，必须保持不提交 GitHub。

当前开发约定：

```bash
ruff check src tests scripts --fix
ruff format src tests scripts
PYTHONPATH=src pytest -q tests/unit
```

最近一次覆盖包阶段的本地验证记录：

```text
PYTHONPATH=src pytest -q tests/unit
61 passed
python -m compileall -q src tests scripts
通过
```

> 注：该记录来自上一轮 v1.4 更新。当前本轮仅更新文档，未新增代码逻辑。

---

### 3.2 Azure 基础资源

已创建 Azure SQL Database 免费数据库。

当前确认状态：

1. SQL 数据库为 Free tier。
2. Pricing tier 为 Free - General Purpose - Serverless。
3. Overage billing 为 Disabled。
4. Azure Cost analysis 当时显示资源组费用为 £0.00。
5. 当前数据库尚未执行任何正式建表 SQL。

重要注意事项：

1. 当前 `sql/migrations/001_create_core_tables.sql` 和 `002_create_indexes.sql` 仍应视为早期草稿，暂不直接执行。
2. 后续建表必须先更新并冻结 `requirements/database_spec.md`，再重写 SQL migration。
3. 一旦 SQL 在 Azure 执行过，后续禁止修改已执行 migration，只能新增 migration。
4. 后续创建 Container Apps、Container Registry、Key Vault、Storage、Log Analytics 等资源后，必须立即检查 Cost analysis。

---

### 3.3 Amazon SP-API 权限和连接

已完成：

```text
SP-API Developer Profile：已获批
Production Private App：已创建
Self Authorization：已完成
LWA Client ID / Secret / Refresh Token：已取得并本地保存
SP-API 本地连接测试：成功
```

当前第一版主站点：

```text
Marketplace: Amazon.com
Country: US
Currency: USD
Marketplace ID: ATVPDKIKX0DER
Region: NA
Endpoint: https://sellingpartnerapi-na.amazon.com
```

已选择的 SP-API Roles：

```text
Finance and Accounting
Selling Partner Insights
Inventory and Order Tracking
Brand Analytics
Amazon Fulfillment
Product Listing
```

当前策略：

1. 暂不主动申请买家 PII 相关权限。
2. 暂不使用 Restricted 税务发票、税款汇缴、买家通讯等高敏感权限。
3. 季度报税目标定位为“会计数据包”，不是系统直接执行税务申报。

---

## 4. 已完成的 SP-API Reports 本地取样能力

### 4.1 Local Sampling Mode

已实现本地取样模式，暂不依赖数据库建表。

核心流程：

```text
submit_report_requests.py
  -> createReport
  -> runtime/sampling/report_requests/{report_id}.json

collect_ready_reports.py
  -> getReport
  -> getReportDocument
  -> download presigned URL
  -> reports/raw/amazon/{marketplace_id}/{report_type}/{date}/{report_id}.txt
  -> runtime/sampling/raw_files/{report_id}.json
```

已实现能力：

1. `createReport` 主动提交普通 Reports API 报告。
2. `getReports` 发现 Amazon 自动生成的 settlement reports。
3. `getReport` 轮询状态。
4. `getReportDocument` 获取下载地址。
5. 支持 gzip 解压。
6. 支持 FATAL diagnostic document 下载。
7. 本地保存 request manifest / raw file manifest。
8. raw file 不提交 GitHub，仅提交脱敏字段样例文档。
9. 支持通用 raw report analyzer。
10. 支持 flat file 与 JSON report 自动识别。

重要目录：

```text
reports/raw/                  # 本地真实 Amazon raw report，不提交 GitHub
runtime/sampling/             # 本地 manifest，不提交 GitHub
requirements/data_samples/    # 脱敏字段样例与结构分析，可提交 GitHub
```

---

### 4.2 批量取样计划

已新增批量取样计划：

```text
requirements/amazon_report_sampling_plan.md
scripts/run_sampling_plan.py
src/seller_data_pipeline/sampling/report_sampling_plan.py
```

支持：

1. `--dry-run` 查看取样清单。
2. 默认批量提交/发现非敏感报告。
3. `--only-report-type` 单独取样某个 report type。
4. `--include-sensitive` 显式加入可能含 PII/客户评论的敏感报告。
5. `--force` 强制重新提交已存在取样任务。
6. reportOptions 模板解析，例如 Promotion / Coupon 的日期参数。
7. 默认避免重复提交已成功、已失败、已取消或已下载诊断文件的同类任务。

当前策略：默认取样尽量覆盖运营与财务有用数据，但避开明显客户 PII 报告。

---

## 5. 已成功取样并分析的数据源

### 5.1 已下载业务 raw report 并生成字段样例的数据源

| 数据域 | report_type | 当前状态 | 主要用途 |
|---|---|---|---|
| Listing | `GET_MERCHANT_LISTINGS_ALL_DATA` | 已下载、已分析、已有 parser | SKU / ASIN / Listing / 价格 / 状态 |
| FBA 库存 | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` | 已下载、已分析、已有 parser | FBA 可售、预留、不可售、入库中库存 |
| 销售与流量 | `GET_SALES_AND_TRAFFIC_REPORT` | 已下载 1 天和 7 天样例、已分析、已有 parser | 日期维度与 PARENT ASIN 维度销售、流量、转化 |
| Settlement 财务 | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | 已发现并下载 8 份、已聚合分析、已有 parser | 结算周期、收入、退款、Amazon fee、FBA fee、广告扣费、促销扣费、赔偿等 |
| 订单明细 | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` | 已下载、已分析、已有 parser | order item 维度销售订单明细 |
| 退货 | `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` | 已下载 header-only、已有 parser | 退货字段已确认，仍需含数据样例 |
| FBA 赔偿 | `GET_FBA_REIMBURSEMENTS_DATA` | 已下载、已分析、已有 parser | 赔偿事件、赔偿数量、赔偿金额 |
| FBA 费用预估 | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` | 已下载、已分析、已有 parser | SKU/ASIN 维度预估 referral fee / fulfillment fee |
| 库存健康 | `GET_FBA_INVENTORY_PLANNING_DATA` | 已下载、已分析、已有 parser | 库存健康、周转、建议补货等 |
| 库存流水汇总 | `GET_LEDGER_SUMMARY_VIEW_DATA` | 已下载、已分析、已有 parser | 每日库存流水汇总 |
| 库存流水明细 | `GET_LEDGER_DETAIL_VIEW_DATA` | 已下载、已分析、已有 parser | 订单/调整/收货等库存事件明细 |
| 预留库存 | `GET_RESERVED_INVENTORY_DATA` | 已下载、已分析、已有 parser | reserved inventory 拆分 |
| 补货建议 | `GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT` | 已下载、已分析、已有 parser | 补货推荐与库存规划 |
| Promotion 效果 | `GET_PROMOTION_PERFORMANCE_REPORT` | 已下载、已分析、已有 parser | 促销活动曝光、销量、收入、included products |
| Coupon 效果 | `GET_COUPON_PERFORMANCE_REPORT` | 已下载、已分析、已有 parser | Coupon 预算、领取、兑换、折扣、销售、ASIN 关联 |

---

### 5.2 已生成/维护的字段样例文档

已生成：

```text
requirements/data_samples/GET_MERCHANT_LISTINGS_ALL_DATA.md
requirements/data_samples/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA.md
requirements/data_samples/GET_SALES_AND_TRAFFIC_REPORT.md
requirements/data_samples/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.md
requirements/data_samples/GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL.md
requirements/data_samples/GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE.md
requirements/data_samples/GET_FBA_REIMBURSEMENTS_DATA.md
requirements/data_samples/GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA.md
requirements/data_samples/GET_FBA_INVENTORY_PLANNING_DATA.md
requirements/data_samples/GET_LEDGER_SUMMARY_VIEW_DATA.md
requirements/data_samples/GET_LEDGER_DETAIL_VIEW_DATA.md
requirements/data_samples/GET_RESERVED_INVENTORY_DATA.md
requirements/data_samples/GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT.md
requirements/data_samples/GET_PROMOTION_PERFORMANCE_REPORT.md
requirements/data_samples/GET_COUPON_PERFORMANCE_REPORT.md
requirements/data_samples/GET_PROMOTION_PERFORMANCE_REPORT_DIAGNOSTIC.md
requirements/data_samples/GET_COUPON_PERFORMANCE_REPORT_DIAGNOSTIC.md
```

注意：这些文档应只保存脱敏后的 header、字段统计、样例值、映射建议和设计结论。真实 raw file 仍保存在本地 `reports/raw/`，不得提交。

---

### 5.3 已新增的 parser 草案

已新增或增强：

```text
src/seller_data_pipeline/parsers/amazon/listings_all_data_parser.py
src/seller_data_pipeline/parsers/amazon/fba_inventory_parser.py
src/seller_data_pipeline/parsers/amazon/sales_report_parser.py
src/seller_data_pipeline/parsers/amazon/settlement_report_parser.py
src/seller_data_pipeline/parsers/amazon/orders_report_parser.py
src/seller_data_pipeline/parsers/amazon/returns_report_parser.py
src/seller_data_pipeline/parsers/amazon/fba_reimbursements_parser.py
src/seller_data_pipeline/parsers/amazon/fba_estimated_fees_parser.py
src/seller_data_pipeline/parsers/amazon/inventory_planning_parser.py
src/seller_data_pipeline/parsers/amazon/inventory_ledger_parser.py
src/seller_data_pipeline/parsers/amazon/reserved_inventory_parser.py
src/seller_data_pipeline/parsers/amazon/restock_inventory_parser.py
src/seller_data_pipeline/parsers/amazon/promotion_coupon_parser.py
src/seller_data_pipeline/parsers/amazon/flat_file_utils.py
```

当前 parser 目标是：

1. 基于真实 raw report 验证字段结构。
2. 输出内存里的标准化 records。
3. 暂不写数据库。
4. 为后续 repository/upsert 逻辑做准备。

---

## 6. 关键数据源设计结论

### 6.1 Listing 与库存要分开

`GET_MERCHANT_LISTINGS_ALL_DATA` 适合做 Listing/SKU/ASIN 快照，但不适合作为 FBA 真实可售库存来源。

原因：真实样例中 `quantity`、`pending-quantity` 为空，而履约渠道是 `AMAZON_NA`。FBA 可售库存应优先来自：

```text
GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA
```

库存主口径建议：

```text
afn-fulfillable-quantity
```

---

### 6.2 销售与流量报告是 JSON

`GET_SALES_AND_TRAFFIC_REPORT` 是 JSON，不是 flat file。

已确认：

1. 日期维度 `salesAndTrafficByDate` 可用。
2. 7 天窗口下 `salesAndTrafficByAsin` 有 PARENT ASIN 维度数据。
3. 适合设计：

```text
amazon_sales_traffic_daily
amazon_sales_traffic_asin_daily
```

---

### 6.3 Settlement 是利润核算的财务事实来源

`GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` 是利润核算最重要的数据源之一。

重要结构特点：

1. 每份 settlement report 第一行通常是 summary 行。
2. summary 行包含结算周期、币种、deposit date、total amount。
3. 后续交易明细行的这些 summary 字段通常为空。
4. parser 必须把 summary 元数据向下继承到明细行。
5. 当前已建立第一版 `amount_category` / `profit_bucket` 分类。

后续利润核算中，真实费用侧优先使用 Settlement，而不是运营报告里的估算值。

---

### 6.4 Promotion / Coupon 是运营效果口径，不是最终财务事实口径

Promotion / Coupon Performance report 已成功取样。

口径：

1. Promotion / Coupon report：看活动效果，例如曝光、销量、销售额、预算、领取、兑换。
2. Settlement report：算真实扣费、实际结算和利润。

Promotion / Coupon 报告提交时必须带专用 `reportOptions`：

```text
promotionStartDateFrom / promotionStartDateTo
couponStartDateFrom / couponStartDateTo
```

---

### 6.5 已取消/失败的可选报告暂不阻塞

以下报告在当前账号/当前时间窗口中出现 `CANCELLED`：

```text
GET_FBA_STORAGE_FEE_CHARGES_DATA
GET_STRANDED_INVENTORY_UI_DATA
GET_FBA_RECOMMENDED_REMOVAL_DATA
GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA
GET_FBA_OVERAGE_FEE_CHARGES_DATA
```

当前判断：大概率是该期间没有可生成数据、报告不适用或账号当前没有相关费用/库存状态。它们不阻塞第一版数据库设计。

后续可以：

1. 在更长时间或特定费用发生后重试。
2. 先从 Settlement 中捕获相关费用扣款。
3. 将这些 report type 保留为可选取样项，不作为建库前置条件。

---

## 7. Amazon Ads API 当前状态

### 7.1 已完成代码准备

上一阶段已经新增 Ads API 取样准备代码：

```text
src/seller_data_pipeline/integrations/amazon/ads_api_client.py
src/seller_data_pipeline/sampling/ads_manifest_store.py
src/seller_data_pipeline/sampling/ads_raw_report_files.py
src/seller_data_pipeline/sampling/ads_report_sampling_plan.py
src/seller_data_pipeline/services/discover_ads_profiles_service.py
src/seller_data_pipeline/services/submit_ads_report_requests_service.py
src/seller_data_pipeline/services/collect_ads_reports_service.py
scripts/discover_ads_profiles.py
scripts/submit_ads_report_requests.py
scripts/run_ads_sampling_plan.py
scripts/collect_ads_reports.py
requirements/amazon_ads_sampling_plan.md
```

默认 Ads 取样计划：

```text
spCampaigns
spTargeting
spSearchTerm
spAdvertisedProduct
spPurchasedProduct
```

### 7.2 当前恢复条件已满足

用户确认 Ads API 申请已经通过，并已准备以下变量：

```text
AMAZON_ADS_REGION
AMAZON_ADS_API_ENDPOINT
AMAZON_ADS_CLIENT_ID
AMAZON_ADS_CLIENT_SECRET
AMAZON_ADS_REFRESH_TOKEN
AMAZON_ADS_PROFILE_ID
AMAZON_ADS_USER_AGENT
```

因此 Ads 取样从“暂停”切换为“sampling”。不过在下载真实 Ads raw report 前，`database_spec.md` 中 Ads normalized 表仍保持 `draft/sampling candidate`，暂不进入 SQL migration。

### 7.3 当前 Ads 最短执行顺序

第一步，只读自检，不提交报告：

```powershell
PYTHONPATH=src python scripts/test_ads_api_connection.py --json
```

如果还没确定 profile，先查看 profiles：

```powershell
PYTHONPATH=src python scripts/test_ads_api_connection.py
```

选择 US / Amazon.com 对应 profile 后写入 `.env`：

```text
AMAZON_ADS_PROFILE_ID='...'
```

第二步，先看计划，不请求 Amazon：

```powershell
PYTHONPATH=src python scripts/run_ads_sampling_plan.py --dry-run --limit 1 --days 3
```

第三步，只提交一个 canary 报告，优先 `spCampaigns`：

```powershell
PYTHONPATH=src python scripts/run_ads_sampling_plan.py --only-report-type-id spCampaigns --limit 1 --days 3
```

第四步，轮询并下载：

```powershell
PYTHONPATH=src python scripts/collect_ads_reports.py --limit 5
```

第五步，对下载到的 raw JSON 生成脱敏字段样例：

```powershell
PYTHONPATH=src python scripts/analyze_ads_raw_report.py `
  --raw-file reports/raw/amazon_ads/{profile_id}/spCampaigns/{date}/{ads_report_id}.json `
  --profile-id {profile_id} `
  --report-type-id spCampaigns `
  --output-md requirements/data_samples/ADS_spCampaigns.md `
  --validate-parser
```

注意：Ads API 用于 campaign / targeting / search term 运营分析；利润核算中的广告真实扣费仍优先使用 Settlement V2。

### 7.4 当前 Ads 取样结果

已完成：

```text
US profile = 3917953989967300
spCampaigns: COMPLETED / DOWNLOADED / normalized_rows=8
spTargeting: COMPLETED / DOWNLOADED / normalized_rows=99
spSearchTerm: COMPLETED / DOWNLOADED / normalized_rows=61
```

已生成或应生成：

```text
requirements/data_samples/ADS_spCampaigns.md
requirements/data_samples/ADS_spTargeting.md
requirements/data_samples/ADS_spSearchTerm.md
```

新增批量分析命令：

```powershell
python scripts/analyze_ads_downloaded_reports.py --profile-id 3917953989967300 --report-type-id spCampaigns --report-type-id spTargeting --report-type-id spSearchTerm --validate-parser
```

下一步优先：

```powershell
python scripts/run_ads_sampling_plan.py --only-report-type-id spSearchTerm --limit 1 --days 3
python scripts/collect_ads_reports.py --limit 5
python scripts/analyze_ads_downloaded_reports.py --profile-id 3917953989967300 --report-type-id spSearchTerm --validate-parser
```

---

## 8. 当前数据库设计状态

数据库唯一事实文档：

```text
requirements/database_spec.md
```

当前数据库状态：

```text
Azure SQL 已开通
尚未建表
尚未执行 sql/migrations/*.sql
```

当前 `database_spec.md` 已根据真实样例覆盖多个 normalized 表草案。第一批建库候选可以分为：

### 8.1 L0/L1 控制与 raw archive 层，建议第一批建

```text
amazon_marketplace
amazon_sync_run_log
amazon_report_request
amazon_raw_report_file
amazon_report_field_catalog
```

作用：记录 report 请求、下载、状态、raw file、字段发现结果。

### 8.2 第一批 normalized 业务表候选

建议优先建与周报/月报强相关、样例已确认的表：

```text
amazon_listing_snapshot
amazon_inventory_daily
amazon_sales_traffic_daily
amazon_sales_traffic_asin_daily
amazon_order_item
amazon_settlement_transaction
amazon_fba_reimbursement
amazon_fba_fee_preview
amazon_inventory_ledger_summary_daily
amazon_inventory_ledger_detail
amazon_reserved_inventory_daily
amazon_inventory_planning_daily
amazon_promotion_performance
amazon_promotion_product_performance
amazon_coupon_performance
amazon_coupon_asin
```

### 8.3 第二批或可选表

```text
amazon_return_request              # 当前只有 header-only 样例，建议保留但低优先级
amazon_restock_inventory_recommendation
amazon_ads_profile
amazon_ads_sp_campaign_daily
amazon_ads_sp_targeting_daily
amazon_ads_sp_search_term_daily
# Ads 四张非空核心表已纳入 SQL 草案但当前仍不执行 SQL
# amazon_ads_sp_purchased_product_daily 当前 3 天窗口为空，暂不进入第一批 SQL
storage_fee / overage / stranded / removal 相关表 # 当前报告多为 CANCELLED，先低优先级
```

---

## 9. 下一阶段推荐计划

Ads API 已经跑通 Sponsored Products 第一批 canary：四个非空 confirmed 报表，以及一个空窗口的 `spPurchasedProduct`。下一阶段不再继续追加同类 canary，优先冻结 Ads 四张非空核心表 schema，并准备 repository/upsert；SQL 执行仍按用户要求暂时搁置。

### Phase A：整理并冻结 database_spec.md 第一批表

目标：把当前已取样成功的数据源，从“采样草案”整理为“第一批建库候选”。

要做：

1. 通读 `requirements/database_spec.md`。
2. 检查表名、字段名、类型、主键/唯一键是否统一。
3. 明确字段来源：report type、原始字段名、parser 字段名。
4. 明确金额字段单位、币种字段、日期字段时区。
5. 明确哪些字段进正式列，哪些保留在 `raw_data`。
6. 明确每张表的 `source_report_id`、`source_raw_file_path`、`source_row_hash`。
7. 明确哪些表第一批建，哪些表第二批建。

验收标准：

```text
database_spec.md 中第一批表达到 confirmed 或 ready_for_sql 状态
```

---

### Phase B：重写 SQL migration，但仍先不执行

目标：根据 `database_spec.md` 重写 SQL。

建议处理：

1. 因数据库尚未建表，可以直接重写：

```text
sql/migrations/001_create_core_tables.sql
sql/migrations/002_create_indexes.sql
```

2. 不要再保留旧草稿中与 spec 不一致的字段。
3. SQL Server / Azure SQL 类型要统一，例如：
   - `NVARCHAR` 用于文本
   - `DECIMAL(18, 4)` 或更高精度用于金额/数量
   - `DATETIME2` 用于时间
   - `DATE` 用于日期维度
4. 索引优先围绕：
   - `marketplace_id`
   - `seller_sku`
   - `asin`
   - `order_id`
   - `report_type`
   - `source_report_id`
   - 日期字段
5. 所有表建议保留：

```text
created_at
updated_at
source_report_id
source_raw_file_path
source_row_hash
raw_data
```

视表用途可裁剪。

验收标准：

```text
SQL migration 与 database_spec.md 一致
尚未执行到 Azure 前，可继续改
```

---

### Phase C：实现数据库连接与 repository 层

目标：把当前本地 manifest/raw 模式升级为可写 Azure SQL，但仍保留 raw file 归档。

建议新增或完善：

```text
src/seller_data_pipeline/db/azure_sql.py
src/seller_data_pipeline/repositories/report_request_repository.py
src/seller_data_pipeline/repositories/raw_report_file_repository.py
src/seller_data_pipeline/repositories/*_repository.py
```

第一阶段 repository 重点：

1. 插入/更新 `amazon_report_request`。
2. 插入/更新 `amazon_raw_report_file`。
3. 写入 `amazon_sync_run_log`。
4. 对第一批 normalized 表做 upsert。

注意：Local Sampling Mode 仍应保留，用于开发取样和排查问题。

---

### Phase D：parser 到数据库入库链路

目标：把已写好的 parser 输出写入 normalized 表。

建议先从低风险表开始：

```text
amazon_listing_snapshot
amazon_inventory_daily
amazon_sales_traffic_daily
amazon_sales_traffic_asin_daily
```

再进入财务复杂表：

```text
amazon_settlement_transaction
amazon_order_item
amazon_fba_reimbursement
amazon_fba_fee_preview
```

财务表先保留明细，不急于做最终利润汇总。

---

### Phase E：利润分类和报表逻辑

目标：基于 Settlement + Orders + Sales + Inventory 建立第一版利润核算。

第一版建议：

1. Settlement 是财务事实主来源。
2. Orders / Sales report 用于运营口径校验。
3. FBA fee preview 用于 SKU 维度预估，不作为最终财务事实。
4. Promotion / Coupon report 用于活动效果，不作为最终财务扣费事实。
5. 广告费在 Ads API 未接入前，先从 Settlement 中归类。

需要建立：

```text
amount_category -> profit_bucket -> report line item
```

例如：

```text
product_sales -> revenue
refund_revenue -> refund
referral_fee -> amazon_fee
fba_fulfillment_fee -> fba_fee
advertising_fee -> advertising_cost
promotion_discount -> promotion_cost
coupon_fee -> promotion_fee
inventory_reimbursement -> reimbursement
```

---

### Phase F：Excel 报表 MVP

等入库链路和基础利润逻辑完成后，再做：

```text
weekly_report_builder.py
monthly_report_builder.py
quarterly_tax_package_builder.py
excel_builder.py
```

第一版报表目标：

1. 店铺总体销售额、订单数、销量。
2. SKU/ASIN 销售与库存。
3. Settlement 费用归类。
4. 初步利润核算。
5. 活动/Coupon 效果摘要。
6. 库存风险与补货建议。

---

### Phase G：Azure 云端部署

最后再进入：

```text
Azure Container Apps Job
Azure Key Vault
Azure Blob Storage
Azure SQL scheduled sync
Email sending
```

不要在数据库 schema 和本地同步链路未稳定前急着部署。

---

## 10. 当前不要做的事

现阶段不建议：

1. 立即执行现有 SQL migration。
2. 立即做完整 Excel 报表。
3. 立即上 Azure Container Apps。
4. 立即写复杂利润汇总表。
5. 继续推进 Ads API 取样，除非 Ads API 已开通。
6. 把 `reports/raw/` 或 `runtime/` 里的真实经营数据提交到 GitHub。
7. 使用含客户 PII 的敏感报告，除非明确需要且已做好脱敏/权限设计。

---

## 11. 安全与数据注意事项

### 11.1 不提交敏感信息

禁止提交：

```text
.env
local_credentials_notes.md
Amazon refresh token
LWA client secret
Ads refresh token
Azure SQL password
SMTP password
任何真实 token 或 secret
reports/raw/
runtime/
```

### 11.2 日志脱敏

日志中不得输出完整：

```text
access_token
refresh_token
client_secret
database password
```

如需排查，只输出前后几位并打码。

### 11.3 原始数据和样例文档分离

真实经营数据只保存在本地或未来的安全存储中：

```text
reports/raw/
runtime/sampling/
```

可提交 GitHub 的只有脱敏后的：

```text
requirements/data_samples/*.md
```

### 11.4 支持回刷和幂等

未来每日同步不应只拉昨天数据。

建议原则：

```text
销售/订单/库存：滚动回刷最近 30-45 天
Settlement：发现最近 89 天内已生成报告
Promotion/Coupon：按活动开始时间窗口回刷
入库：全部使用 upsert 或 source_row_hash 去重
```

原因：

1. 广告和销售归因会延迟。
2. 退款会延迟。
3. 赔偿和调整会延迟。
4. 财务结算与订单发生日期不完全一致。

### 11.5 季度报税包需要版本锁定

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

## 12. 当前里程碑状态

| Milestone | 状态 | 说明 |
|---|---|---|
| M1 项目骨架与 CI | 已完成 | 项目结构、测试、Ruff 规则已建立 |
| M2 Azure SQL 免费库 | 已完成但未建表 | 数据库已开通，SQL 尚未执行 |
| M3 SP-API 权限与连接 | 已完成 | Developer Profile、Private App、自授权、连接测试完成 |
| M4 Reports API Local Sampling Mode | 已完成 | createReport / getReports / collect / download / manifest 完成 |
| M5 核心 SP-API 数据源取样 | 基本完成 | Listing、库存、销售、订单、Settlement、赔偿、活动等已取样 |
| M6 Parser 草案 | 基本完成 | 多个 parser 已根据真实样例编写，暂不入库 |
| M7 Database Spec | 进行中 | 已持续更新，下一步应冻结第一批建库表 |
| M8 SQL migration | 未开始/待重写 | 等 spec 冻结后重写 001/002 |
| M9 Azure SQL 入库 | 未开始 | 等 SQL 建表后实现 repository/upsert |
| M10 报表生成 | 未开始 | 等入库和利润逻辑完成后做 |
| M11 Ads API 取样 | sampling_confirmed_core_sp | Ads API 已开通；SP 五个 canary 均已提交下载，其中四个非空，spPurchasedProduct 当前窗口为空 |
| M12 云端部署 | 未开始 | 等本地链路稳定后再部署 |

---

## 13. 下一步一句话目标

下一步核心目标是：

```text
继续 Ads API 取样，但仍搁置 SQL 执行；先补 spSearchTerm canary，确认搜索词字段和 parser，再决定是否把 Ads 第一批表加入下一版 SQL。
```

推荐最近一次开发任务：

```text
提交 spSearchTerm 3 天 canary
  -> collect_ads_reports.py 下载 raw JSON
  -> analyze_ads_downloaded_reports.py 生成 ADS_spSearchTerm.md
  -> 确认搜索词、花费、订单、销售字段是否稳定
  -> 暂不执行 Azure SQL
```

---

## v1.10 Ads API 当前结果补充

本节已被 v1.11 结果更新覆盖。`spPurchasedProduct` 已完成 canary，但当前 3 天窗口为空；以 v1.11 结论为准。

## v1.11 Ads API 当前结果补充

本阶段 SQL 执行继续搁置，Ads 主线完成 Sponsored Products 第一批 canary：

| reportTypeId | 结果 | normalized_rows | 处理结论 |
|---|---|---:|---|
| `spCampaigns` | `COMPLETED / DOWNLOADED / PARSED` | 8 | campaign 表可进入第一批 SQL 草案 |
| `spTargeting` | `COMPLETED / DOWNLOADED / PARSED` | 99 | targeting 表可进入第一批 SQL 草案 |
| `spSearchTerm` | `COMPLETED / DOWNLOADED / PARSED` | 61 | search term 表可进入第一批 SQL 草案 |
| `spAdvertisedProduct` | `COMPLETED / DOWNLOADED / PARSED` | 32 | advertised product 表可进入第一批 SQL 草案 |
| `spPurchasedProduct` | `COMPLETED / DOWNLOADED / EMPTY` | 0 | API 与 parser 均正常，但当前窗口没有 purchased product 归因行；暂不建表 |

关键判断：`spPurchasedProduct` 返回空数组不是失败。它说明当前 2026-05-12 至 2026-05-15 窗口没有可观测的点击后购买 ASIN 归因，或样本量不足。后续若要建 `amazon_ads_sp_purchased_product_daily`，建议先用 14/30 天窗口补一次非空样例。

下一步建议二选一：

1. 回到 SQL 执行前准备，人工复核当前 migration。
2. 继续 Ads 入库开发，先实现四张非空 confirmed 表的 repository/upsert：campaign、targeting、search term、advertised product。


---

## v1.12 字段漂移守门与 raw file 留存规则

本轮根据运营要求补充后续持续自动任务的稳定性设计：

1. 所有 Amazon 下载文件必须先保存 raw file；即使 parser 失败、字段不匹配、报表为空，也必须保留。
2. 下载后立即执行 schema validation，先比较 observed fields 与 expected fields，再进入 parser / upsert。
3. 当前代码优先覆盖 Amazon Ads JSON reports：`spCampaigns`、`spTargeting`、`spSearchTerm`、`spAdvertisedProduct`、`spPurchasedProduct`。
4. `spPurchasedProduct` 当前为空，标记为 `empty_report` / `sampling_confirmed_empty`，暂不据此建表。
5. 新增 `amazon_schema_validation_event` SQL 草案，用于未来 Azure SQL 中记录字段漂移、缺失字段、新字段、通知状态。
6. 后续自动任务如果出现 schema drift、parser failed、upsert failed，需要写任务审计并邮件通知检查 raw file 和更新表结构。
7. 数据库创建完成后，`requirements/database_spec.md` 继续作为数据库唯一事实文档，所有表结构变更先改 spec，再写 migration。

新增脚本：

```powershell
python scripts/validate_ads_downloaded_reports_schema.py --profile-id 3917953989967300 --report-type-id spCampaigns --report-type-id spTargeting --report-type-id spSearchTerm --report-type-id spAdvertisedProduct --report-type-id spPurchasedProduct
```

也可以在批量样例分析时顺带校验：

```powershell
python scripts/analyze_ads_downloaded_reports.py --profile-id 3917953989967300 --validate-parser --validate-schema
```

当前 SQL 仍然只是草案，不执行 Azure SQL。

---

## 16. v1.13 Ads 入库前 dry-run 守门链路

本阶段不连接 Azure SQL、不执行 migration、不发送真实邮件，只把未来自动任务中最容易出问题的部分提前固化：

```text
已下载 raw file
    -> schema validation
    -> Ads parser
    -> 目标表字段映射
    -> business_key_hash
    -> 本地 DB-ready preview JSONL
    -> schema_validation_events.jsonl
    -> task_audit_event.json
```

新增入口：

```powershell
python scripts/prepare_ads_ingestion.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER
```

当前用真实已下载 Ads raw reports 验证结果：

```text
processed_files=4
parsed_rows=200
prepared_rows=200
preview_files=4
requires_review=False
```

输出位置：

```text
runtime/ingestion/amazon_ads/{profile_id}/{YYYYMMDD_HHMMSS}/
    ads_ingestion_summary.json
    task_audit_event.json
    schema_validation_events.jsonl
    previews/
        amazon_ads_sp_campaign_daily.preview.jsonl
        amazon_ads_sp_targeting_daily.preview.jsonl
        amazon_ads_sp_search_term_daily.preview.jsonl
        amazon_ads_sp_advertised_product_daily.preview.jsonl
```

### 16.1 business_key_hash 规则

每个目标表都保留：

```text
source_row_hash      # 用于追溯 raw row，包含 source row index
business_key_hash    # 用于未来 upsert，基于稳定业务键
```

`source_row_hash` 不适合作为长期 upsert 唯一键，因为同一日期范围重跑报表时，文件、行号或排序可能变化。`business_key_hash` 用目标表名 + 业务键字段生成，适合后续唯一索引和幂等 upsert。

Ads 四张核心表第一版业务键：

| 目标表 | 业务键字段 |
|---|---|
| `amazon_ads_sp_campaign_daily` | `profile_id + report_date + campaign_id` |
| `amazon_ads_sp_targeting_daily` | `profile_id + report_date + campaign_id + ad_group_id + keyword_id + targeting + match_type` |
| `amazon_ads_sp_search_term_daily` | `profile_id + report_date + campaign_id + ad_group_id + keyword_id + targeting + search_term + match_type` |
| `amazon_ads_sp_advertised_product_daily` | `profile_id + report_date + campaign_id + ad_group_id + advertised_asin + advertised_sku` |

### 16.2 入库前阻断规则

以下 schema validation 状态会阻断 dry-run 入库准备，并在未来真实工作流里触发邮件通知：

```text
missing_fields
new_fields
schema_drift
unmapped_fields
validation_failed
empty_report_unexpected
```

`empty_report` 本身不阻断，但不能据此设计新表。`spPurchasedProduct` 目前属于 `sampling_confirmed_empty`，不进入第一批 Ads 表。

### 16.3 下一步计划

1. 人工抽查四个 `.preview.jsonl`，确认字段、业务键和 row count 合理。
2. 回到 Azure SQL 执行线，运行连接测试和 001/002 migration。
3. 新增真实 repository/upsert，把 v1.13 的 preview rows 写入 Azure SQL。
4. 将 `task_audit_event.json` 写入 `amazon_sync_run_log`。
5. 将 `schema_validation_events.jsonl` 写入 `amazon_schema_validation_event`。
6. 接入邮件通知：字段漂移、parser 失败、upsert 失败、任务异常退出时通知。

