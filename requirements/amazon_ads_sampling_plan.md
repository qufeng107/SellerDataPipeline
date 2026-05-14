# Amazon Ads API 取样计划（唯一事实辅助文档）

版本：v0.1  
状态：sampling  
最后更新：2026-05-14

## 1. 目标

SP-API Reports 已经覆盖 Listing、库存、订单、销售流量、财务结算、赔偿、优惠券和促销等数据源。下一阶段补充 Amazon Ads API，用于获取广告运营口径数据：

- Campaign 表现
- Targeting / Keyword 表现
- Search Term 表现
- Advertised Product 表现
- Purchased Product / halo sales 表现

这些数据用于广告优化，不直接替代财务口径。利润核算中的广告实际扣费仍优先以 Settlement report 为准；Ads API 用于解释广告花费来自哪些 campaign、关键词、搜索词和 ASIN。

## 2. 与 SP-API Reports 的区别

| 项目 | SP-API Reports | Amazon Ads API |
|---|---|---|
| 认证 | SP-API LWA refresh token | Ads LWA refresh token |
| 账号维度 | marketplace / seller | profileId / advertiser account |
| 报告流程 | createReport / getReport / getReportDocument | Reporting v3 create / status / URL download |
| 主要用途 | 经营、库存、订单、财务 | 广告投放和效果优化 |
| 本地 raw 路径 | `reports/raw/amazon/...` | `reports/raw/amazon_ads/...` |

## 3. 配置项

`.env` 中新增：

```text
AMAZON_ADS_API_ENDPOINT='https://advertising-api.amazon.com'
AMAZON_ADS_CLIENT_ID=''
AMAZON_ADS_CLIENT_SECRET=''
AMAZON_ADS_REFRESH_TOKEN=''
AMAZON_ADS_PROFILE_ID=''
```

说明：

- `AMAZON_ADS_CLIENT_ID` / `AMAZON_ADS_CLIENT_SECRET` 为空时，会 fallback 到 `AMAZON_LWA_CLIENT_ID` / `AMAZON_LWA_CLIENT_SECRET`。
- `AMAZON_ADS_REFRESH_TOKEN` 必须是 Ads API 授权得到的 refresh token，不应默认复用 SP-API refresh token。
- `AMAZON_ADS_PROFILE_ID` 可以通过 `scripts/discover_ads_profiles.py` 发现。

## 4. 本地取样流程

### 4.1 发现 profiles

```bash
PYTHONPATH=src python scripts/discover_ads_profiles.py
```

输出保存到：

```text
runtime/sampling/ads_profiles.json
```

### 4.2 查看默认计划

```bash
PYTHONPATH=src python scripts/run_ads_sampling_plan.py --dry-run
```

### 4.3 提交默认取样计划

```bash
PYTHONPATH=src python scripts/run_ads_sampling_plan.py
```

### 4.4 轮询并下载

```bash
PYTHONPATH=src python scripts/collect_ads_reports.py --limit 20
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

## 5. 默认 Sponsored Products 取样清单

| reportTypeId | groupBy | timeUnit | 用途 | 状态 |
|---|---|---|---|---|
| `spCampaigns` | `campaign` | DAILY | campaign 级广告花费、点击、销售、订单 | sampling |
| `spTargeting` | `targeting` | DAILY | keyword / targeting 级表现 | sampling |
| `spSearchTerm` | `searchTerm` | DAILY | 用户搜索词表现，用于找词和否词 | sampling |
| `spAdvertisedProduct` | `advertiser` | DAILY | 被广告推广的 SKU / ASIN 表现 | sampling |
| `spPurchasedProduct` | `asin` | DAILY | 点击广告后实际购买 ASIN，用于 halo sales 分析 | sampling |

## 6. 待确认事项

1. 当前店铺是否已有 Ads API refresh token。
2. `profileId` 是否与当前 US marketplace 的广告账户一致。
3. Sponsored Products 报告字段是否全部被账号接受。
4. SP seller 账号销售归因窗口优先采用 `sales7d` / `purchases7d`，后续根据真实字段确认。
5. 是否需要补 Sponsored Brands / Sponsored Display。当前先不默认请求，避免扩大复杂度。

## 7. 后续入库草案

真实 Ads raw report 下载并解析后，再把以下表从 draft 推进到 sampling/confirmed：

- `amazon_ads_profile`
- `amazon_ads_sp_campaign_daily`
- `amazon_ads_sp_targeting_daily`
- `amazon_ads_sp_search_term_daily`
- `amazon_ads_sp_advertised_product_daily`
- `amazon_ads_sp_purchased_product_daily`

在正式建库前，仍然遵守：

```text
先 raw，后 normalized。
先样例，后字段。
先 spec，后 SQL。
```
