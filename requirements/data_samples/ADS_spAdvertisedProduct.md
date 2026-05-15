# spAdvertisedProduct 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `amazon_ads` |
| report_type | `spAdvertisedProduct` |
| marketplace_id | `3917953989967300` |
| raw_file_path | `reports\raw\amazon_ads\3917953989967300\spAdvertisedProduct\2026-05-15\b6754b6b-482b-4169-8fe3-86e0af5065b3.json` |
| file_format | `json` |
| encoding | `utf-8-sig` |
| delimiter | `n/a` |
| row_count | `32` |
| field_path_count | `13` |

## 2. 结构备注

- top-level array length = 32

## 3. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `[].adGroupId` | 32 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `454581494673074`, `419199069884035` |
| 2 | `[].adGroupName` | 32 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:15 chars>`, `<redacted:17 chars>` |
| 3 | `[].advertisedAsin` | 32 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 4 | `[].advertisedSku` | 32 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 5 | `[].campaignId` | 32 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `16958304007203`, `21666157974301` |
| 6 | `[].campaignName` | 32 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:15 chars>`, `<redacted:17 chars>` |
| 7 | `[].clicks` | 32 | 0 | 1.00 | 10 | `integer` | `mapped_candidate` | `2`, `3`, `0`, `1`, `4` |
| 8 | `[].cost` | 32 | 0 | 1.00 | 22 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 9 | `[].date` | 32 | 0 | 1.00 | 4 | `datetime_string` | `mapped_candidate` | `2026-05-12`, `2026-05-13`, `2026-05-14`, `2026-05-15` |
| 10 | `[].impressions` | 32 | 0 | 1.00 | 32 | `integer` | `mapped_candidate` | `448`, `269`, `374`, `119`, `99` |
| 11 | `[].purchases7d` | 32 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `1` |
| 12 | `[].sales7d` | 32 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |
| 13 | `[].unitsSoldClicks7d` | 32 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |

## 4. 初步结论

1. 本报告已通过真实 Amazon Ads API canary 下载并解析，本次样例包含 32 行。
2. Ads API 是广告运营归因口径，适合解释 campaign、关键词、搜索词或 ASIN 维度表现；利润核算中的广告真实扣费仍优先以 Settlement V2 为财务口径。
3. 本报告第一版 parser 采用通用 Ads normalized row，正式入库前再按 reportTypeId 拆到目标明细表。

## 5. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_ads_sp_advertised_product_daily` | `sampling_confirmed` | Advertised SKU/ASIN daily metrics for product-level advertising analysis. 暂不执行 SQL |
