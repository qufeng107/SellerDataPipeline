# GET_COUPON_PERFORMANCE_REPORT 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_COUPON_PERFORMANCE_REPORT` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_COUPON_PERFORMANCE_REPORT/2026-05-14/112492020587.txt` |
| file_format | `json` |
| encoding | `utf-8-sig` |
| delimiter | `n/a` |
| row_count | `2` |
| field_path_count | `23` |

## 2. 结构备注

- `coupons` array length = 2

## 3. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `coupons[].asins[].asin` | 4 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 2 | `coupons[].budget` | 2 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `100.0`, `600.0` |
| 3 | `coupons[].budgetPercentageUsed` | 2 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `42.645` |
| 4 | `coupons[].budgetRemaining` | 2 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `100.0`, `344.13` |
| 5 | `coupons[].budgetSpent` | 2 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `255.87` |
| 6 | `coupons[].clips` | 2 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `113` |
| 7 | `coupons[].couponId` | 2 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `AH8IU6C8T6PTX`, `ALHFCPRV7JR1U` |
| 8 | `coupons[].currencyCode` | 2 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 9 | `coupons[].discountAmount` | 2 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |
| 10 | `coupons[].discountType` | 2 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `AMOUNT_OFF_LIST_PRICE`, `PERCENT_OFF_LIST_PRICE` |
| 11 | `coupons[].endDateTime` | 2 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `2026-06-01T06:59:59Z`, `2026-04-01T06:59:59Z` |
| 12 | `coupons[].marketplaceId` | 2 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `ATVPDKIKX0DER` |
| 13 | `coupons[].merchantId` | 2 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `A3MX5L1C1J86AB` |
| 14 | `coupons[].name` | 2 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:33 chars>`, `<redacted:38 chars>` |
| 15 | `coupons[].redemptions` | 2 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `33` |
| 16 | `coupons[].sales` | 2 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>` |
| 17 | `coupons[].startDateTime` | 2 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `2026-05-13T07:00:00Z`, `2026-03-25T07:00:00Z` |
| 18 | `coupons[].totalDiscount` | 2 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `255.87` |
| 19 | `coupons[].websiteMessage` | 2 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:33 chars>`, `<redacted:38 chars>` |
| 20 | `reportSpecification.marketplaceIds[]` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `ATVPDKIKX0DER` |
| 21 | `reportSpecification.reportOptions.couponStartDateFrom` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `2026-02-14T00:00:00Z` |
| 22 | `reportSpecification.reportOptions.couponStartDateTo` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `2026-05-14T00:00:00Z` |
| 23 | `reportSpecification.reportType` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `GET_COUPON_PERFORMANCE_REPORT` |

## 4. 初步结论

1. 本报告是 JSON 格式，用于 Coupon 活动效果分析；第一版利润核算仍以 Settlement V2 的 Coupon/促销扣费口径为准。
2. 本次样例包含 `coupons` 2 行；每个 coupon 下面可能包含多个 ASIN，因此建议拆成 Coupon 主表和 Coupon-ASIN 明细表。
3. `budgetSpent`、`totalDiscount`、`redemptions`、`sales` 适合评估 Coupon 使用效果，但不应直接替代结算中的实际费用。

## 5. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_coupon_performance` | `sampling` | Coupon 主表，记录预算、领取、兑换、销售等指标，暂不执行 SQL |
| `amazon_coupon_asin` | `sampling` | Coupon 关联 ASIN 明细，暂不执行 SQL |
