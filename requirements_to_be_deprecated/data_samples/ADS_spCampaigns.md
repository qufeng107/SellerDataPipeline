# spCampaigns 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `amazon_ads` |
| report_type | `spCampaigns` |
| marketplace_id | `3917953989967300` |
| raw_file_path | `reports\raw\amazon_ads\3917953989967300\spCampaigns\2026-05-15\5dc8e80b-72cc-4e37-864f-e877b7f90e5c.json` |
| file_format | `json` |
| encoding | `utf-8-sig` |
| delimiter | `n/a` |
| row_count | `8` |
| field_path_count | `10` |

## 2. 结构备注

- top-level array length = 8

## 3. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `[].campaignId` | 8 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `16958304007203`, `21666157974301` |
| 2 | `[].campaignName` | 8 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:15 chars>`, `<redacted:17 chars>` |
| 3 | `[].campaignStatus` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `ENABLED` |
| 4 | `[].clicks` | 8 | 0 | 1.00 | 8 | `integer` | `mapped_candidate` | `16`, `18`, `19`, `8`, `12` |
| 5 | `[].cost` | 8 | 0 | 1.00 | 8 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 6 | `[].date` | 8 | 0 | 1.00 | 4 | `datetime_string` | `mapped_candidate` | `2026-05-12`, `2026-05-13`, `2026-05-14`, `2026-05-15` |
| 7 | `[].impressions` | 8 | 0 | 1.00 | 8 | `integer` | `mapped_candidate` | `4651`, `4701`, `7137`, `3738`, `1160` |
| 8 | `[].purchases7d` | 8 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `1`, `0` |
| 9 | `[].sales7d` | 8 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |
| 10 | `[].unitsSoldClicks7d` | 8 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |

## 4. 初步结论

1. 本报告已通过真实 Amazon Ads API canary 下载并解析，本次样例包含 8 行。
2. Ads API 是广告运营归因口径，适合解释 campaign、关键词、搜索词或 ASIN 维度表现；利润核算中的广告真实扣费仍优先以 Settlement V2 为财务口径。
3. 本报告第一版 parser 采用通用 Ads normalized row，正式入库前再按 reportTypeId 拆到目标明细表。

## 5. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_ads_sp_campaign_daily` | `sampling_confirmed` | Campaign-level Sponsored Products daily metrics for spend, clicks, sales and orders. 暂不执行 SQL |
