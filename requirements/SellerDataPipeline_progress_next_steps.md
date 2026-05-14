# SellerDataPipeline 当前进展与下一步计划

> 更新时间：2026-05-14  
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

Amazon Ads API 相关取样代码已经准备，但用户确认 **Ads API 尚未开通**，因此 Ads 数据源先暂停，不影响 SP-API 主线继续推进。

---

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

### 7.2 当前暂停原因

用户确认：

```text
Amazon Ads API 尚未开通
```

因此 Ads 取样暂时停止，不继续运行 Ads 脚本，也暂不根据 Ads 数据设计正式表。

当前 `database_spec.md` 中 Ads 相关表应保持：

```text
draft
```

### 7.3 后续恢复条件

等 Ads API 开通后再执行：

```powershell
python scripts/discover_ads_profiles.py
```

选择 US 广告 profile 后写入 `.env`：

```text
AMAZON_ADS_PROFILE_ID='...'
```

再运行：

```powershell
python scripts/run_ads_sampling_plan.py --dry-run
python scripts/run_ads_sampling_plan.py
python scripts/collect_ads_reports.py --limit 20
```

注意：Ads API 用于 campaign / targeting / search term 运营分析；利润核算中的广告真实扣费仍优先使用 Settlement V2。

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
amazon_ads_*                       # Ads API 未开通，保持 draft
storage_fee / overage / stranded / removal 相关表 # 当前报告多为 CANCELLED，先低优先级
```

---

## 9. 下一阶段推荐计划

由于 Ads API 暂未开通，下一阶段不要继续 Ads，而应转向 **冻结 SP-API 数据库设计与准备建库**。

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
| M11 Ads API 取样 | 暂停 | 代码已准备，但 Ads API 尚未开通 |
| M12 云端部署 | 未开始 | 等本地链路稳定后再部署 |

---

## 13. 下一步一句话目标

下一步核心目标是：

```text
暂停 Ads API，整理并冻结 SP-API 已取样数据源的 database_spec.md 第一批建库范围，随后重写 SQL migration，但在确认前仍不执行建表。
```

推荐最近一次开发任务：

```text
检查 database_spec.md
  -> 标记第一批表 ready_for_sql
  -> 重写 001_create_core_tables.sql / 002_create_indexes.sql
  -> 代码暂不接数据库
  -> 人工复核 SQL
  -> 再决定是否执行 Azure SQL 建表
```
