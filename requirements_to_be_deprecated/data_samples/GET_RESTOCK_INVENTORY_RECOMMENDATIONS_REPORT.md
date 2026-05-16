# GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT/2026-05-14/112481020587.txt` |
| file_format | `delimited` |
| encoding | `cp1252` |
| delimiter | `tab` |
| row_count | `5` |
| field_path_count | `30` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `Country` | 5 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `US` |
| 2 | `Product Name` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:179 chars>`, `<redacted:178 chars>`, `<redacted:185 chars>`, `<redacted:179 chars>`, `<redacted:182 chars>` |
| 3 | `FNSKU` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 4 | `Merchant SKU` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 5 | `ASIN` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 6 | `Condition` | 5 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `New` |
| 7 | `Supplier` | 5 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `unassigned` |
| 8 | `Supplier part no.` | 0 | 5 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 9 | `Currency code` | 5 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `USD` |
| 10 | `Price` | 5 | 0 | 1.00 | 3 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 11 | `Sales last 30 days` | 5 | 0 | 1.00 | 5 | `decimal` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 12 | `Units Sold Last 30 Days` | 5 | 0 | 1.00 | 5 | `integer` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 13 | `Total Units` | 5 | 0 | 1.00 | 5 | `integer` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 14 | `Inbound` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 15 | `Available` | 5 | 0 | 1.00 | 5 | `integer` | `mapped_candidate` | `731`, `219`, `0`, `114`, `277` |
| 16 | `FC transfer` | 5 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `3`, `0`, `1` |
| 17 | `FC Processing` | 5 | 0 | 1.00 | 5 | `integer` | `mapped_candidate` | `5`, `7`, `1`, `2`, `6` |
| 18 | `Customer Order` | 5 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `1`, `0` |
| 19 | `Unfulfillable` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 20 | `Working` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 21 | `Shipped` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 22 | `Receiving` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 23 | `Fulfilled by` | 5 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `Amazon` |
| 24 | `Total Days of Supply (including units from open shipments)` | 5 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `365+`, `<redacted:numeric>` |
| 25 | `Days of Supply at Amazon Fulfillment Network` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `207`, `274`, `0`, `179`, `365+` |
| 26 | `Alert` | 1 | 4 | 0.20 | 1 | `string` | `mapped_candidate` | `out_of_stock` |
| 27 | `Recommended replenishment qty` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:numeric>` |
| 28 | `Recommended ship date` | 5 | 0 | 1.00 | 1 | `datetime_string` | `mapped_candidate` | `none` |
| 29 | `Recommended action` | 5 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `No action required` |
| 30 | `Unit storage size` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `0.0356 ft3`, `0.0319 ft3`, `0.2329 ft3`, `0.0267 ft3`, `0.0315 ft3` |

## 3. 初步结论

1. 本报告已完成字段统计，但目标 normalized 表仍需人工确认。
2. 原始字段先保留在 raw file 和 `raw_data` 中，避免过早丢失信息。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| 待确认 | `sampling` | 需要结合业务用途和后续样例确认 |
