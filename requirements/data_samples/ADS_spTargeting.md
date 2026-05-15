# spTargeting 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `amazon_ads` |
| report_type | `spTargeting` |
| marketplace_id | `3917953989967300` |
| raw_file_path | `reports\raw\amazon_ads\3917953989967300\spTargeting\2026-05-15\c89e0e82-be20-468d-8ec7-884a1d623e9f.json` |
| file_format | `json` |
| encoding | `utf-8-sig` |
| delimiter | `n/a` |
| row_count | `99` |
| field_path_count | `15` |

## 2. 结构备注

- top-level array length = 99

## 3. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `[].adGroupId` | 99 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `454581494673074`, `419199069884035` |
| 2 | `[].adGroupName` | 99 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:15 chars>`, `<redacted:17 chars>` |
| 3 | `[].campaignId` | 99 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `16958304007203`, `21666157974301` |
| 4 | `[].campaignName` | 99 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:15 chars>`, `<redacted:17 chars>` |
| 5 | `[].clicks` | 99 | 0 | 1.00 | 8 | `integer` | `mapped_candidate` | `0`, `1`, `2`, `6`, `7` |
| 6 | `[].cost` | 99 | 0 | 1.00 | 24 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 7 | `[].date` | 99 | 0 | 1.00 | 4 | `datetime_string` | `mapped_candidate` | `2026-05-12`, `2026-05-13`, `2026-05-14`, `2026-05-15` |
| 8 | `[].impressions` | 99 | 0 | 1.00 | 74 | `integer` | `mapped_candidate` | `12`, `10`, `7`, `341`, `224` |
| 9 | `[].keyword` | 99 | 0 | 1.00 | 18 | `string` | `mapped_candidate` | `<redacted:25 chars>`, `<redacted:15 chars>`, `<redacted:15 chars>`, `<redacted:20 chars>`, `<redacted:20 chars>` |
| 10 | `[].keywordId` | 99 | 0 | 1.00 | 27 | `integer` | `mapped_candidate` | `<redacted:15 chars>`, `<redacted:15 chars>`, `<redacted:14 chars>`, `<redacted:14 chars>`, `<redacted:15 chars>` |
| 11 | `[].matchType` | 99 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `EXACT`, `PHRASE`, `TARGETING_EXPRESSION_PREDEFINED` |
| 12 | `[].purchases7d` | 99 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `1` |
| 13 | `[].sales7d` | 99 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |
| 14 | `[].targeting` | 99 | 0 | 1.00 | 18 | `string` | `mapped_candidate` | `<redacted:25 chars>`, `<redacted:15 chars>`, `<redacted:15 chars>`, `<redacted:20 chars>`, `<redacted:20 chars>` |
| 15 | `[].unitsSoldClicks7d` | 99 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |

## 4. 初步结论

1. 本报告已通过真实 Amazon Ads API canary 下载并解析，本次样例包含 99 行。
2. Ads API 是广告运营归因口径，适合解释 campaign、关键词、搜索词或 ASIN 维度表现；利润核算中的广告真实扣费仍优先以 Settlement V2 为财务口径。
3. 本报告第一版 parser 采用通用 Ads normalized row，正式入库前再按 reportTypeId 拆到目标明细表。

## 5. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_ads_sp_targeting_daily` | `sampling_confirmed` | Keyword/target-level Sponsored Products daily metrics for bid and targeting optimization. 暂不执行 SQL |
