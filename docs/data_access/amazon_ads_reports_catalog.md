# Amazon Ads API 数据接入目录

> 更新时间：2026-05-16  
> 文档定位：记录本项目通过 Amazon Ads API 可以接入的 profile 与 Sponsored Products 报告。本文只描述数据接入能力，不定义广告优化功能或数据库设计。

## 1. 账号与认证维度

Amazon Ads API 与 SP-API Reports 是不同的数据入口：

| 项目 | Amazon Ads API |
|---|---|
| 账号维度 | `profileId` / advertiser account |
| 当前已确认 US profile | `3917953989967300` |
| 当前 US marketplace | `ATVPDKIKX0DER` |
| 主要接口 | Profiles API + Reporting v3 |
| 当前 raw 路径 | `reports/raw/amazon_ads/{profile_id}/{report_type_id}/{date}/{ads_report_id}.json` |
| 当前用途边界 | 广告归因与运营分析口径；财务入账口径仍应优先看 settlement 中的广告扣费。 |

Profiles API 当前用于发现可访问的 Ads profile、国家、币种、账号类型、payment method 等信息。当前真实数据库已有 `amazon_ads_profile` 表，但本目录只记录数据入口，不维护表结构。

## 2. Reporting v3 获取流程

```text
Submit Ads report request
  -> poll report status
  -> download report URL
  -> save raw JSON
  -> analyze source fields
```

当前脚本入口包括：

```text
scripts/test_ads_api_connection.py
scripts/discover_ads_profiles.py
scripts/submit_ads_report_requests.py
scripts/collect_ads_reports.py
scripts/run_ads_sampling_plan.py
scripts/analyze_ads_raw_report.py
scripts/analyze_ads_downloaded_reports.py
```

## 3. 当前已验证 Sponsored Products 报告

### spCampaigns

| Item | Value |
|---|---|
| Source | Amazon Ads API Reporting v3 |
| adProduct | `SPONSORED_PRODUCTS` |
| reportTypeId | `spCampaigns` |
| groupBy used in current sampling | `campaign` |
| timeUnit | `DAILY` |
| Current sample file | `requirements/data_samples/ADS_spCampaigns.md` |
| Format | `json` top-level array |
| Current sample rows | `8` |
| Observed field/path count | `10` |
| Status | `sampled + analyzed + real ingestion verified` |
| Data domain | Sponsored Products campaign-level daily metrics. |

Observed source fields:

`[].campaignId`, `[].campaignName`, `[].campaignStatus`, `[].clicks`, `[].cost`, `[].date`, `[].impressions`, `[].purchases7d`, `[].sales7d`, `[].unitsSoldClicks7d`

### spTargeting

| Item | Value |
|---|---|
| Source | Amazon Ads API Reporting v3 |
| adProduct | `SPONSORED_PRODUCTS` |
| reportTypeId | `spTargeting` |
| groupBy used in current sampling | `targeting` |
| timeUnit | `DAILY` |
| Current sample file | `requirements/data_samples/ADS_spTargeting.md` |
| Format | `json` top-level array |
| Current sample rows | `99` |
| Observed field/path count | `15` |
| Status | `sampled + analyzed + real ingestion verified` |
| Data domain | Sponsored Products keyword/targeting-level daily metrics. |

Observed source fields:

`[].adGroupId`, `[].adGroupName`, `[].campaignId`, `[].campaignName`, `[].clicks`, `[].cost`, `[].date`, `[].impressions`, `[].keyword`, `[].keywordId`, `[].matchType`, `[].purchases7d`, `[].sales7d`, `[].targeting`, `[].unitsSoldClicks7d`

### spSearchTerm

| Item | Value |
|---|---|
| Source | Amazon Ads API Reporting v3 |
| adProduct | `SPONSORED_PRODUCTS` |
| reportTypeId | `spSearchTerm` |
| groupBy used in current sampling | `searchTerm` |
| timeUnit | `DAILY` |
| Current sample file | `requirements/data_samples/ADS_spSearchTerm.md` |
| Format | `json` top-level array |
| Current sample rows | `61` |
| Observed field/path count | `16` |
| Status | `sampled + analyzed + real ingestion verified` |
| Data domain | Sponsored Products shopper search term daily metrics. |

Observed source fields:

`[].adGroupId`, `[].adGroupName`, `[].campaignId`, `[].campaignName`, `[].clicks`, `[].cost`, `[].date`, `[].impressions`, `[].keyword`, `[].keywordId`, `[].matchType`, `[].purchases7d`, `[].sales7d`, `[].searchTerm`, `[].targeting`, `[].unitsSoldClicks7d`

### spAdvertisedProduct

| Item | Value |
|---|---|
| Source | Amazon Ads API Reporting v3 |
| adProduct | `SPONSORED_PRODUCTS` |
| reportTypeId | `spAdvertisedProduct` |
| groupBy used in current sampling | `advertiser` |
| timeUnit | `DAILY` |
| Current sample file | `requirements/data_samples/ADS_spAdvertisedProduct.md` |
| Format | `json` top-level array |
| Current sample rows | `32` |
| Observed field/path count | `13` |
| Status | `sampled + analyzed + real ingestion verified` |
| Data domain | Sponsored Products advertised SKU/ASIN daily metrics. |

Observed source fields:

`[].adGroupId`, `[].adGroupName`, `[].advertisedAsin`, `[].advertisedSku`, `[].campaignId`, `[].campaignName`, `[].clicks`, `[].cost`, `[].date`, `[].impressions`, `[].purchases7d`, `[].sales7d`, `[].unitsSoldClicks7d`

### spPurchasedProduct

| Item | Value |
|---|---|
| Source | Amazon Ads API Reporting v3 |
| adProduct | `SPONSORED_PRODUCTS` |
| reportTypeId | `spPurchasedProduct` |
| groupBy used in current sampling | `asin` |
| timeUnit | `DAILY` |
| Current sample file | `requirements/data_samples/ADS_spPurchasedProduct.md` |
| Format | `json` top-level array |
| Current sample rows | `0` |
| Observed field/path count | `1` |
| Status | `sampled empty` |
| Data domain | Purchased ASIN attribution after ad clicks; current sample is empty. |

Observed source fields:

`[]`

## 4. 当前入库验证状态说明

以下四类报告已经完成真实 Azure SQL 入库和幂等性验证：

| reportTypeId | First execute | Second execute | 当前表行数 |
|---|---:|---:|---:|
| `spCampaigns` | inserted=8 | updated=8 | 8 |
| `spTargeting` | inserted=99 | updated=99 | 99 |
| `spSearchTerm` | inserted=61 | updated=61 | 61 |
| `spAdvertisedProduct` | inserted=32 | updated=32 | 32 |

`spPurchasedProduct` 当前 3 天窗口返回空数组，说明该窗口没有可观测 purchased product 归因行；这不是 API 或 parser 失败。后续如果要启用该数据，应先用更长窗口补非空样例。

## 5. Sponsored Brands / Sponsored Display

当前没有把 Sponsored Brands 或 Sponsored Display 纳入第一批数据接入。后续如需要，必须先在本目录新增对应 data access 记录，再建立功能文档和数据库变更计划。
