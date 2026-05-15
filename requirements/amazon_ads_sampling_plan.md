# Amazon Ads API 取样计划（唯一事实辅助文档）

版本：v0.6  
状态：sampling_confirmed_core_sp_with_empty_purchased_product  
最后更新：2026-05-15

## 1. 当前结论

Amazon Ads API 已经开通，当前不再暂停 Ads 主线。SQL 执行仍然搁置，Ads 本轮目标是先完成：

```text
只读连接自检：已完成
  -> profiles 发现与 AMAZON_ADS_PROFILE_ID 确认：已完成，US profile=3917953989967300
  -> spCampaigns canary：已完成，8 行
  -> spTargeting canary：已完成，99 行
  -> spSearchTerm canary：已完成，61 行
  -> spAdvertisedProduct canary：已完成，32 行
  -> spPurchasedProduct canary：已完成下载但空数组，0 行，标记 sampling_confirmed_empty
  -> 生成脱敏字段样例文档：已完成 ADS_spCampaigns / spTargeting / spSearchTerm / spAdvertisedProduct / spPurchasedProduct
```

Amazon Ads API 报告用于广告运营分析，不直接替代财务口径。利润核算中的广告真实扣费仍优先以 Settlement report 为准；Ads API 用于解释广告花费来自哪些 campaign、关键词、搜索词和 ASIN。

## 2. 与 SP-API Reports 的区别

| 项目 | SP-API Reports | Amazon Ads API |
|---|---|---|
| 认证 | SP-API LWA refresh token | Ads LWA refresh token |
| 账号维度 | marketplace / seller | profileId / advertiser account |
| 报告流程 | createReport / getReport / getReportDocument | Reporting v3 create / status / URL download |
| 主要用途 | 经营、库存、订单、财务 | 广告投放和效果优化 |
| 本地 raw 路径 | `reports/raw/amazon/...` | `reports/raw/amazon_ads/...` |

## 3. 配置项

`.env` 中新增或确认：

```text
AMAZON_ADS_REGION='NA'
AMAZON_ADS_API_ENDPOINT='https://advertising-api.amazon.com'
AMAZON_ADS_CLIENT_ID=''
AMAZON_ADS_CLIENT_SECRET=''
AMAZON_ADS_REFRESH_TOKEN=''
AMAZON_ADS_PROFILE_ID=''
AMAZON_ADS_USER_AGENT='SellerDataPipeline/0.1.0 (Language=Python/3.11)'
```

说明：

1. `AMAZON_ADS_CLIENT_ID` / `AMAZON_ADS_CLIENT_SECRET` 为空时，会 fallback 到 `AMAZON_LWA_CLIENT_ID` / `AMAZON_LWA_CLIENT_SECRET`。
2. `AMAZON_ADS_REFRESH_TOKEN` 必须是 Ads API 授权得到的 refresh token，不应默认复用 SP-API refresh token。
3. `AMAZON_ADS_REGION` 为空时会 fallback 到 `AMAZON_REGION`，默认 `NA`。
4. `AMAZON_ADS_API_ENDPOINT` 已显式配置时，以显式配置为准。Amazon.com / US 一般使用 `https://advertising-api.amazon.com`。
5. `AMAZON_ADS_PROFILE_ID` 可以通过只读连接自检或 profile discovery 发现。

## 4. 本地取样流程

### 4.1 只读连接自检

先验证 LWA refresh token 和 profiles，不提交任何报告：

```bash
PYTHONPATH=src python scripts/test_ads_api_connection.py
PYTHONPATH=src python scripts/test_ads_api_connection.py --json
```

成功后会显示可访问的 profile 列表。优先选择：

```text
countryCode = US
currencyCode = USD
accountInfo.type = seller
accountInfo.validPaymentMethod = true
accountInfo.marketplaceStringId = ATVPDKIKX0DER
```

然后写入 `.env`：

```text
AMAZON_ADS_PROFILE_ID='...'
```

### 4.2 保存 profiles manifest

```bash
PYTHONPATH=src python scripts/discover_ads_profiles.py
```

输出保存到：

```text
runtime/sampling/ads_profiles.json
```

### 4.3 先做 canary dry-run

```bash
PYTHONPATH=src python scripts/run_ads_sampling_plan.py --dry-run --limit 1 --days 3
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = "src"
python scripts/run_ads_sampling_plan.py --dry-run --limit 1 --days 3
```

### 4.4 提交一个 canary 报告

第一份只建议提交 `spCampaigns`，时间窗口缩短为 3 天，避免一开始就触发太多异步报告或字段错误：

```bash
PYTHONPATH=src python scripts/run_ads_sampling_plan.py \
  --only-report-type-id spCampaigns \
  --limit 1 \
  --days 3
```

Windows PowerShell 单行写法：

```powershell
$env:PYTHONPATH = "src"
python scripts/run_ads_sampling_plan.py --only-report-type-id spCampaigns --limit 1 --days 3
```

### 4.5 轮询并下载

```bash
PYTHONPATH=src python scripts/collect_ads_reports.py --limit 5
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = "src"
python scripts/collect_ads_reports.py --limit 5
```

下载文件保存到：

```text
reports/raw/amazon_ads/{profile_id}/{report_type_id}/{date}/{ads_report_id}.json
```

manifest 保存到：

```text
runtime/sampling/ads_report_requests/{ads_report_id}.json
runtime/sampling/ads_raw_files/{ads_report_id}.json
```

下载完成后，`collect_ads_reports.py` 会尝试运行通用 `AdsReportParser`，并在 request/raw manifest 中写入：

```text
parse_status
normalized_row_count
parse_error_message
```

### 4.6 生成脱敏字段样例

推荐优先用 `--latest`，避免手工替换 `{profile_id}` / `{date}` / `{ads_report_id}`：

```bash
PYTHONPATH=src python scripts/analyze_ads_raw_report.py \
  --latest \
  --profile-id 3917953989967300 \
  --report-type-id spCampaigns \
  --output-md requirements/data_samples/ADS_spCampaigns.md \
  --validate-parser
```

Windows PowerShell 单行写法：

```powershell
$env:PYTHONPATH = "src"
python scripts/analyze_ads_raw_report.py --latest --profile-id 3917953989967300 --report-type-id spCampaigns --output-md requirements/data_samples/ADS_spCampaigns.md --validate-parser
```

也可以显式传入真实 raw file 路径，不要保留花括号占位符：

```powershell
python scripts/analyze_ads_raw_report.py --raw-file "reports\raw\amazon_ads\3917953989967300\spCampaigns\2026-05-15\5dc8e80b-72cc-4e37-864f-e877b7f90e5c.json" --profile-id 3917953989967300 --report-type-id spCampaigns --output-md requirements/data_samples/ADS_spCampaigns.md --validate-parser
```

真实 raw file 不提交 GitHub；`requirements/data_samples/ADS_*.md` 只保留字段统计和脱敏样例。

## 5. 当前已完成真实 Ads 样例

| reportTypeId | 状态 | 日期窗口 | raw 行数 | normalized 行数 | 样例文档 | 目标表状态 |
|---|---|---|---:|---:|---|---|
| `spCampaigns` | completed | 2026-05-12 至 2026-05-15 | 8 | 8 | `requirements/data_samples/ADS_spCampaigns.md` | `sampling_confirmed` |
| `spTargeting` | completed | 2026-05-12 至 2026-05-15 | 99 | 99 | `requirements/data_samples/ADS_spTargeting.md` | `sampling_confirmed` |
| `spSearchTerm` | completed | 2026-05-12 至 2026-05-15 | 61 | 61 | `requirements/data_samples/ADS_spSearchTerm.md` | `sampling_confirmed` |
| `spAdvertisedProduct` | completed | 2026-05-12 至 2026-05-15 | 32 | 32 | `requirements/data_samples/ADS_spAdvertisedProduct.md` | `sampling_confirmed` |
| `spPurchasedProduct` | completed_empty | 2026-05-12 至 2026-05-15 | 0 | 0 | `requirements/data_samples/ADS_spPurchasedProduct.md` | `sampling_confirmed_empty` |

注意：`keyword`、`keywordId`、`targeting`、`searchTerm` 属于广告投放策略数据，样例文档必须脱敏；真实 raw file 仍只保留在本地或后续安全存储中，不提交 GitHub。

批量更新已下载 Ads 样例文档：

```powershell
python scripts/analyze_ads_downloaded_reports.py --profile-id 3917953989967300 --report-type-id spCampaigns --report-type-id spTargeting --report-type-id spSearchTerm --report-type-id spAdvertisedProduct --validate-parser
```

## 6. 默认 Sponsored Products 取样清单

| 执行顺序 | reportTypeId | groupBy | timeUnit | 用途 | 当前策略 |
|---:|---|---|---|---|---|
| 1 | `spCampaigns` | `campaign` | DAILY | campaign 级广告花费、点击、销售、订单 | 已完成 3 天 canary |
| 2 | `spTargeting` | `targeting` | DAILY | keyword / targeting 级表现 | 已完成 3 天 canary |
| 3 | `spSearchTerm` | `searchTerm` | DAILY | 用户搜索词表现，用于找词和否词 | 已完成 3 天 canary |
| 4 | `spAdvertisedProduct` | `advertiser` | DAILY | 被广告推广的 SKU / ASIN 表现 | 已完成 3 天 canary，groupBy=advertiser 被当前账号接受 |
| 5 | `spPurchasedProduct` | `asin` | DAILY | 点击广告后实际购买 ASIN，用于 halo sales 分析 | 已完成 3 天 canary；API 接受但本窗口空数组，后续可用 14/30 天窗口补有行样例 |

## 7. 待确认事项

1. `profileId` 是否与当前 US marketplace 的广告账户一致。
2. 默认 Sponsored Products 报告字段是否全部被账号接受。
3. `spAdvertisedProduct` 的 `groupBy=advertiser` 已被当前账号接受，当前样例 32 行。
4. `spPurchasedProduct` 的 `groupBy=asin` 与第一版列清单已被当前账号接受，但 3 天窗口返回空数组；后续需要用更长窗口补含数据行样例后再建正式表。
5. SP seller 账号销售归因窗口先采用 `sales7d` / `purchases7d`，后续根据真实字段确认。
6. 是否需要补 Sponsored Brands / Sponsored Display。当前先不默认请求，避免扩大复杂度。

## 8. 后续入库草案

`spCampaigns` / `spTargeting` / `spSearchTerm` / `spAdvertisedProduct` 已从 candidate 推进到 `sampling_confirmed`；四张核心表已纳入 SQL 草案但暂不执行。`spPurchasedProduct` 已完成 canary 但当前样例为空，暂标记为 `sampling_confirmed_empty`，不进入第一批 SQL。其余 Ads 表仍待后续扩展：

- `amazon_ads_profile`
- `amazon_ads_sp_campaign_daily`
- `amazon_ads_sp_targeting_daily`
- `amazon_ads_sp_search_term_daily`
- `amazon_ads_sp_advertised_product_daily`
- `amazon_ads_sp_purchased_product_daily`  # sampling_confirmed_empty，待更长窗口补非空样例

在正式建库前，仍然遵守：

```text
先 raw，后 normalized。
先样例，后字段。
先 spec，后 SQL。
```

## 9. 当前已确认 canary 结果 v1.11

| reportTypeId | 状态 | 样例行数 | 样例文档 | 目标表状态 |
|---|---|---:|---|---|
| `spCampaigns` | `COMPLETED / DOWNLOADED / PARSED` | 8 | `requirements/data_samples/ADS_spCampaigns.md` | `sampling_confirmed` |
| `spTargeting` | `COMPLETED / DOWNLOADED / PARSED` | 99 | `requirements/data_samples/ADS_spTargeting.md` | `sampling_confirmed` |
| `spSearchTerm` | `COMPLETED / DOWNLOADED / PARSED` | 61 | `requirements/data_samples/ADS_spSearchTerm.md` | `sampling_confirmed` |
| `spAdvertisedProduct` | `COMPLETED / DOWNLOADED / PARSED` | 32 | `requirements/data_samples/ADS_spAdvertisedProduct.md` | `sampling_confirmed` |
| `spPurchasedProduct` | `COMPLETED / DOWNLOADED / EMPTY` | 0 | `requirements/data_samples/ADS_spPurchasedProduct.md` | `sampling_confirmed_empty` |

下一步建议：

1. 不再继续追加同类 canary；Sponsored Products 第一批取样已经足够支撑 Ads 核心表设计。
2. `spPurchasedProduct` 当前 3 天窗口为空，不是错误；后续可以在真实入库前用 14/30 天窗口补一次非空样例。
3. 当前优先进入 Ads repository/upsert 设计，或回到 Azure SQL 建表执行通道。

---

## v1.12 字段漂移检测与持续工作流规则

Amazon Ads API 后续进入持续同步后，可能出现以下情况：

1. 报表成功下载但为空，例如当前 `spPurchasedProduct`。
2. Amazon 新增字段。
3. Amazon 去掉或重命名字段。
4. parser 能解析 raw JSON，但入库表字段尚未更新。
5. SQL upsert 因字段类型、长度、唯一键或列不存在失败。

处理原则：

```text
先保留 raw file
    -> 再生成字段取样文档 ADS_*.md
    -> 再执行 schema validation
    -> 如果需要人工审查，邮件通知
    -> 人工确认后更新 database_spec.md
    -> 新增 migration + parser/repository 测试
```

新增校验入口：

```powershell
python scripts/validate_ads_downloaded_reports_schema.py --profile-id 3917953989967300 --report-type-id spCampaigns --report-type-id spTargeting --report-type-id spSearchTerm --report-type-id spAdvertisedProduct --report-type-id spPurchasedProduct
```

输出位置：

```text
runtime/sampling/schema_validation/ADS_<reportTypeId>_schema_validation.json
runtime/sampling/schema_validation/ADS_<reportTypeId>_schema_validation.md
```

`collect_ads_reports.py` 下载完成后，也会把本次 schema validation 摘要写入本地 request manifest 和 raw file manifest，字段包括：

```text
schema_validation_status
schema_validation_severity
schema_validation_requires_review
schema_validation_message
```

后续 Azure SQL 建表后，同类信息写入 `amazon_schema_validation_event`。

---

## v1.13 入库前 dry-run 与长期维护规则

Ads canary 已完成后，不再把重点放在继续扩大取样，而是把已下载 raw reports 转成未来数据库可写入的 DB-ready preview rows。

命令：

```powershell
python scripts/prepare_ads_ingestion.py --profile-id 3917953989967300 --marketplace-id ATVPDKIKX0DER
```

当前四个 table-ready reportTypeId：

```text
spCampaigns
spTargeting
spSearchTerm
spAdvertisedProduct
```

`spPurchasedProduct` 虽然 API 已确认，但当前窗口为空，暂不进入 table-ready mapping。后续需要 14/30 天非空样例后再升级。

输出：

```text
runtime/ingestion/amazon_ads/{profile_id}/{run_timestamp}/ads_ingestion_summary.json
runtime/ingestion/amazon_ads/{profile_id}/{run_timestamp}/task_audit_event.json
runtime/ingestion/amazon_ads/{profile_id}/{run_timestamp}/schema_validation_events.jsonl
runtime/ingestion/amazon_ads/{profile_id}/{run_timestamp}/previews/*.preview.jsonl
```

维护原则：

1. raw file 永久保留；preview 只用于本地审查，不提交 GitHub。
2. `database_spec.md` 是唯一事实，任何字段变化必须先更新 spec。
3. schema validation 出现 `new_fields` / `missing_fields` / `schema_drift` 时，停止入库并通知人工审查。
4. `source_row_hash` 用于追溯 raw row；`business_key_hash` 用于未来幂等 upsert。
5. SQL migration 草案可以更新，但未执行前仍需人工审查；一旦 Azure 执行过，后续只能追加 migration，不能改已执行文件。

