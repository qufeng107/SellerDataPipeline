# GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL/2026-05-14/112467020587.txt` |
| file_format | `delimited` |
| encoding | `utf-8-sig` |
| delimiter | `tab` |
| row_count | `112` |
| field_path_count | `33` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `amazon-order-id` | 112 | 0 | 1.00 | 109 | `string` | `mapped_candidate` | `<redacted:19 chars>`, `<redacted:19 chars>`, `<redacted:19 chars>`, `<redacted:19 chars>`, `<redacted:19 chars>` |
| 2 | `merchant-order-id` | 112 | 0 | 1.00 | 109 | `string` | `mapped_candidate` | `<redacted:9 chars>`, `<redacted:9 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 3 | `purchase-date` | 112 | 0 | 1.00 | 109 | `datetime_string` | `mapped_candidate` | `2026-05-08T23:36:26+00:00`, `2026-05-08T23:35:42+00:00`, `2026-05-03T15:34:18+00:00`, `2026-04-28T09:51:44+00:00`, `2026-04-28T09:46:15+00:00` |
| 4 | `last-updated-date` | 112 | 0 | 1.00 | 109 | `datetime_string` | `mapped_candidate` | `2026-05-08T23:57:05+00:00`, `2026-05-14T12:14:46+00:00`, `2026-05-05T01:04:56+00:00`, `2026-04-28T10:08:15+00:00`, `2026-04-28T09:48:17+00:00` |
| 5 | `order-status` | 112 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `Cancelled`, `Shipping`, `Shipped`, `Pending` |
| 6 | `fulfillment-channel` | 112 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `Amazon` |
| 7 | `sales-channel` | 112 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `Non-Amazon`, `Amazon.com` |
| 8 | `order-channel` | 0 | 112 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 9 | `ship-service-level` | 112 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `Standard`, `Expedited`, `SecondDay` |
| 10 | `product-name` | 112 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:1 chars>`, `<redacted:150 chars>` |
| 11 | `sku` | 112 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 12 | `asin` | 112 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 13 | `item-status` | 112 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `Unshipped`, `Shipped`, `Cancelled` |
| 14 | `quantity` | 112 | 0 | 1.00 | 5 | `integer` | `mapped_candidate` | `1`, `50`, `100`, `2`, `0` |
| 15 | `currency` | 105 | 7 | 0.94 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 16 | `item-price` | 105 | 7 | 0.94 | 9 | `decimal` | `mapped_candidate` | `25.0`, `26.0`, `50.0`, `20.0`, `40.0` |
| 17 | `item-tax` | 97 | 15 | 0.87 | 46 | `decimal` | `mapped_candidate` | `1.66`, `1.81`, `1.56`, `1.5`, `2.22` |
| 18 | `shipping-price` | 38 | 74 | 0.34 | 13 | `decimal` | `mapped_candidate` | `2.99`, `1.5`, `1.49`, `0.6`, `0.59` |
| 19 | `shipping-tax` | 3 | 109 | 0.03 | 3 | `decimal` | `mapped_candidate` | `0.06`, `0.05`, `0.25` |
| 20 | `gift-wrap-price` | 0 | 112 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 21 | `gift-wrap-tax` | 0 | 112 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 22 | `item-promotion-discount` | 0 | 112 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 23 | `ship-promotion-discount` | 35 | 77 | 0.31 | 11 | `decimal` | `mapped_candidate` | `2.99`, `1.5`, `1.49`, `0.6`, `0.59` |
| 24 | `ship-city` | 107 | 5 | 0.96 | 98 | `string` | `mapped_candidate` | `<redacted:5 chars>`, `<redacted:14 chars>`, `<redacted:10 chars>`, `<redacted:14 chars>`, `<redacted:12 chars>` |
| 25 | `ship-state` | 107 | 5 | 0.96 | 39 | `string` | `mapped_candidate` | `<redacted:2 chars>`, `<redacted:2 chars>`, `<redacted:2 chars>`, `<redacted:2 chars>`, `<redacted:2 chars>` |
| 26 | `ship-postal-code` | 107 | 5 | 0.96 | 101 | `string` | `mapped_candidate` | `<redacted:5 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 27 | `ship-country` | 107 | 5 | 0.96 | 3 | `string` | `mapped_candidate` | `US`, `IL`, `PR` |
| 28 | `promotion-ids` | 1 | 111 | 0.01 | 1 | `string` | `mapped_candidate` | `Duplicated A3JU1FCINF5SD0 1569460229772` |
| 29 | `cpf` | 0 | 112 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 30 | `is-business-order` | 112 | 0 | 1.00 | 2 | `boolean_flag` | `mapped_candidate` | `false`, `true` |
| 31 | `purchase-order-number` | 0 | 112 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 32 | `price-designation` | 0 | 112 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 33 | `signature-confirmation-recommended` | 112 | 0 | 1.00 | 1 | `boolean_flag` | `mapped_candidate` | `<redacted:5 chars>` |

## 3. 初步结论

1. 本报告适合生成 `amazon_order_item`，用于订单/行项目维度收入、数量、状态、履约渠道和促销折扣分析。
2. 样例中包含 ship-city / ship-state / ship-postal-code 等地址字段，正式表建议仅保留低敏国家/州/邮编，raw file 仍不得提交 GitHub。
3. 本报告销售金额是订单口径，最终利润仍应以 settlement/finance费用口径做对账。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_order_item` | `sampling` | 已有 30 天真实订单样例，暂不执行 SQL |
