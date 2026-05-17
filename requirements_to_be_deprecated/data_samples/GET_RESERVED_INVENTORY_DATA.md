# GET_RESERVED_INVENTORY_DATA 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_RESERVED_INVENTORY_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_RESERVED_INVENTORY_DATA/2026-05-14/112480020587.txt` |
| file_format | `delimited` |
| encoding | `cp1252` |
| delimiter | `tab` |
| row_count | `5` |
| field_path_count | `9` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `sku` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 2 | `fnsku` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 3 | `asin` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 4 | `product-name` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:178 chars>`, `<redacted:182 chars>`, `<redacted:185 chars>`, `<redacted:179 chars>`, `<redacted:179 chars>` |
| 5 | `reserved_qty` | 5 | 0 | 1.00 | 4 | `integer` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 6 | `reserved_customerorders` | 5 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `1` |
| 7 | `reserved_fc-transfers` | 5 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `0`, `1`, `4` |
| 8 | `reserved_fc-processing` | 5 | 0 | 1.00 | 5 | `integer` | `mapped_candidate` | `7`, `6`, `1`, `2`, `5` |
| 9 | `program` | 0 | 5 | 0.00 | 0 | `string` | `mapped_candidate` | - |

## 3. 初步结论

1. 本报告已完成字段统计，但目标 normalized 表仍需人工确认。
2. 原始字段先保留在 raw file 和 `raw_data` 中，避免过早丢失信息。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| 待确认 | `sampling` | 需要结合业务用途和后续样例确认 |
