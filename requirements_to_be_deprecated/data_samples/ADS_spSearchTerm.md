# spSearchTerm 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `amazon_ads` |
| report_type | `spSearchTerm` |
| marketplace_id | `3917953989967300` |
| raw_file_path | `reports\raw\amazon_ads\3917953989967300\spSearchTerm\2026-05-15\4c38fa3c-8595-40c3-8e9f-2c52e90641a9.json` |
| file_format | `json` |
| encoding | `utf-8-sig` |
| delimiter | `n/a` |
| row_count | `61` |
| field_path_count | `16` |

## 2. 结构备注

- top-level array length = 61

## 3. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `[].adGroupId` | 61 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `419199069884035`, `454581494673074` |
| 2 | `[].adGroupName` | 61 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:17 chars>`, `<redacted:15 chars>` |
| 3 | `[].campaignId` | 61 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `21666157974301`, `16958304007203` |
| 4 | `[].campaignName` | 61 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:17 chars>`, `<redacted:15 chars>` |
| 5 | `[].clicks` | 61 | 0 | 1.00 | 6 | `integer` | `mapped_candidate` | `1`, `2`, `6`, `7`, `5` |
| 6 | `[].cost` | 61 | 0 | 1.00 | 29 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 7 | `[].date` | 61 | 0 | 1.00 | 4 | `datetime_string` | `mapped_candidate` | `2026-05-14`, `2026-05-12`, `2026-05-13`, `2026-05-15` |
| 8 | `[].impressions` | 61 | 0 | 1.00 | 45 | `integer` | `mapped_candidate` | `1`, `2`, `3`, `5`, `6` |
| 9 | `[].keyword` | 61 | 0 | 1.00 | 10 | `string` | `mapped_candidate` | `<redacted:11 chars>`, `<redacted:15 chars>`, `<redacted:11 chars>`, `<redacted:22 chars>`, `<redacted:26 chars>` |
| 10 | `[].keywordId` | 61 | 0 | 1.00 | 13 | `integer` | `mapped_candidate` | `<redacted:15 chars>`, `<redacted:14 chars>`, `<redacted:15 chars>`, `<redacted:15 chars>`, `<redacted:15 chars>` |
| 11 | `[].matchType` | 61 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `TARGETING_EXPRESSION_PREDEFINED`, `PHRASE`, `EXACT` |
| 12 | `[].purchases7d` | 61 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `1` |
| 13 | `[].sales7d` | 61 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |
| 14 | `[].searchTerm` | 61 | 0 | 1.00 | 45 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 15 | `[].targeting` | 61 | 0 | 1.00 | 10 | `string` | `mapped_candidate` | `<redacted:11 chars>`, `<redacted:15 chars>`, `<redacted:11 chars>`, `<redacted:22 chars>`, `<redacted:26 chars>` |
| 16 | `[].unitsSoldClicks7d` | 61 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |

## 4. 初步结论

1. 本报告已通过真实 Amazon Ads API canary 下载并解析，本次样例包含 61 行。
2. Ads API 是广告运营归因口径，适合解释 campaign、关键词、搜索词或 ASIN 维度表现；利润核算中的广告真实扣费仍优先以 Settlement V2 为财务口径。
3. 本报告第一版 parser 采用通用 Ads normalized row，正式入库前再按 reportTypeId 拆到目标明细表。

## 5. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_ads_sp_search_term_daily` | `sampling_confirmed` | Customer search term daily metrics for keyword mining and negative keyword decisions. 暂不执行 SQL |
