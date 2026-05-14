# GET_PROMOTION_PERFORMANCE_REPORT 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_PROMOTION_PERFORMANCE_REPORT` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_PROMOTION_PERFORMANCE_REPORT/2026-05-14/112491020587.txt` |
| file_format | `json` |
| encoding | `utf-8-sig` |
| delimiter | `n/a` |
| row_count | `1` |
| field_path_count | `24` |

## 2. 结构备注

- `promotions` array length = 1

## 3. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `promotions[].createdDateTime` | 1 | 0 | 1.00 | 1 | `datetime_string` | `mapped_candidate` | `2026-03-23T03:25:30Z` |
| 2 | `promotions[].endDateTime` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `2026-03-25T06:59:59Z` |
| 3 | `promotions[].glanceViews` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `435` |
| 4 | `promotions[].includedProducts[].asin` | 3 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 5 | `promotions[].includedProducts[].productGlanceViews` | 3 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `24`, `9`, `402` |
| 6 | `promotions[].includedProducts[].productName` | 3 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `<redacted:182 chars>`, `<redacted:178 chars>`, `<redacted:179 chars>` |
| 7 | `promotions[].includedProducts[].productRevenue` | 3 | 0 | 1.00 | 3 | `decimal` | `mapped_candidate` | `75.88`, `0.0`, `546.81` |
| 8 | `promotions[].includedProducts[].productRevenueCurrencyCode` | 3 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 9 | `promotions[].includedProducts[].productUnitsSold` | 3 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 10 | `promotions[].lastUpdatedDateTime` | 1 | 0 | 1.00 | 1 | `datetime_string` | `mapped_candidate` | `2026-05-09T00:00:00Z` |
| 11 | `promotions[].marketplaceId` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `ATVPDKIKX0DER` |
| 12 | `promotions[].merchantId` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `A3MX5L1C1J86AB` |
| 13 | `promotions[].promotionId` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `79f08a7a` |
| 14 | `promotions[].promotionName` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `<redacted:15 chars>` |
| 15 | `promotions[].revenue` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `622.69` |
| 16 | `promotions[].revenueCurrencyCode` | 1 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 17 | `promotions[].startDateTime` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `2026-03-23T07:00:00Z` |
| 18 | `promotions[].status` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `APPROVED` |
| 19 | `promotions[].type` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `BEST_DEAL` |
| 20 | `promotions[].unitsSold` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:numeric>` |
| 21 | `reportSpecification.marketplaceIds[]` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `ATVPDKIKX0DER` |
| 22 | `reportSpecification.reportOptions.promotionStartDateFrom` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `2026-02-14T00:00:00Z` |
| 23 | `reportSpecification.reportOptions.promotionStartDateTo` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `2026-05-14T00:00:00Z` |
| 24 | `reportSpecification.reportType` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `GET_PROMOTION_PERFORMANCE_REPORT` |

## 4. 初步结论

1. 本报告是 JSON 格式，用于活动效果分析；第一版利润核算仍以 Settlement V2 的财务扣费口径为准。
2. 本次样例包含 `promotions` 1 行；每个 promotion 下面可能包含多个 `includedProducts`，因此建议拆成活动主表和活动商品明细表。
3. `revenue` / `unitsSold` / `glanceViews` 是运营表现口径，不应直接等同于最终利润或结算金额。

## 5. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_promotion_performance` | `sampling` | 活动主表，记录 Deal/Promotion 的总体表现，暂不执行 SQL |
| `amazon_promotion_product_performance` | `sampling` | 活动商品明细表，记录 ASIN 维度表现，暂不执行 SQL |
