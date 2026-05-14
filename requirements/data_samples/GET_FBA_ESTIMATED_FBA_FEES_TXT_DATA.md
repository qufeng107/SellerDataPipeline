# GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA/2026-05-14/112470020587.txt` |
| file_format | `delimited` |
| encoding | `cp1252` |
| delimiter | `tab` |
| row_count | `8` |
| field_path_count | `31` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `sku` | 8 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 2 | `fnsku` | 8 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 3 | `asin` | 8 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 4 | `amazon-store` | 8 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `CA`, `US` |
| 5 | `product-name` | 8 | 0 | 1.00 | 8 | `string` | `mapped_candidate` | `<redacted:39 chars>`, `<redacted:179 chars>`, `<redacted:62 chars>`, `<redacted:178 chars>`, `<redacted:42 chars>` |
| 6 | `product-group` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `Luggage` |
| 7 | `brand` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `Chynotopia` |
| 8 | `fulfilled-by` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `Amazon` |
| 9 | `your-price` | 8 | 0 | 1.00 | 5 | `decimal` | `mapped_candidate` | `51.54`, `25.00`, `51.63`, `53.21`, `26.00` |
| 10 | `sales-price` | 8 | 0 | 1.00 | 5 | `decimal` | `mapped_candidate` | `51.54`, `25.00`, `51.63`, `53.21`, `26.00` |
| 11 | `longest-side` | 8 | 0 | 1.00 | 6 | `decimal` | `mapped_candidate` | `19.61`, `7.72`, `19.71`, `7.76`, `19.89` |
| 12 | `median-side` | 8 | 0 | 1.00 | 8 | `decimal` | `mapped_candidate` | `16.61`, `6.54`, `15.9`, `6.26`, `16.21` |
| 13 | `shortest-side` | 8 | 0 | 1.00 | 8 | `decimal` | `mapped_candidate` | `3.1`, `1.22`, `2.9`, `1.14`, `2.79` |
| 14 | `length-and-girth` | 8 | 0 | 1.00 | 8 | `decimal` | `mapped_candidate` | `59.03`, `23.24`, `57.2`, `22.52`, `57.71` |
| 15 | `unit-of-dimension` | 8 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `centimeters`, `inches` |
| 16 | `item-package-weight` | 8 | 0 | 1.00 | 6 | `decimal` | `mapped_candidate` | `82.01`, `0.18`, `109.0`, `0.24`, `90.99` |
| 17 | `unit-of-weight` | 8 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `grams`, `pounds` |
| 18 | `product-size-tier` | 8 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `Standard`, `UsLargeStandardSize` |
| 19 | `currency` | 8 | 0 | 1.00 | 2 | `currency_code` | `mapped_candidate` | `CAD`, `USD` |
| 20 | `estimated-fee-total` | 8 | 0 | 1.00 | 5 | `decimal` | `mapped_candidate` | `17.89`, `7.80`, `17.90`, `18.14`, `7.95` |
| 21 | `estimated-referral-fee-per-unit` | 8 | 0 | 1.00 | 5 | `decimal` | `mapped_candidate` | `7.73`, `3.75`, `7.74`, `7.98`, `3.90` |
| 22 | `estimated-variable-closing-fee` | 8 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `0.00` |
| 23 | `estimated-order-handling-fee-per-order` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `--` |
| 24 | `estimated-pick-pack-fee-per-unit` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `--` |
| 25 | `estimated-weight-handling-fee-per-unit` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `--` |
| 26 | `expected-fulfillment-fee-per-unit` | 8 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `10.16`, `4.05` |
| 27 | `estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `--` |
| 28 | `estimated-future-order-handling-fee-per-order` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `--` |
| 29 | `estimated-future-pick-pack-fee-per-unit` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `--` |
| 30 | `estimated-future-weight-handling-fee-per-unit` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `--` |
| 31 | `expected-future-fulfillment-fee-per-unit` | 8 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `--` |

## 3. 初步结论

1. 本报告适合生成 `amazon_fba_fee_preview`，用于 SKU/ASIN 维度预估 referral fee 和 fulfillment fee。
2. 样例包含 `amazon-store`，同一 SKU 可能出现 US/CA 等站点行，正式唯一键应包含 store 或 marketplace。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_fba_fee_preview` | `sampling` | 已有真实样例，暂不执行 SQL |
