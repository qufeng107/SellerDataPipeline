# GET_LEDGER_DETAIL_VIEW_DATA 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_LEDGER_DETAIL_VIEW_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_LEDGER_DETAIL_VIEW_DATA/2026-05-14/112479020587.txt` |
| file_format | `delimited` |
| encoding | `utf-8-sig` |
| delimiter | `tab` |
| row_count | `207` |
| field_path_count | `16` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `Date` | 207 | 0 | 1.00 | 30 | `datetime_string` | `mapped_candidate` | `05/13/2026`, `05/12/2026`, `05/11/2026`, `05/10/2026`, `05/09/2026` |
| 2 | `FNSKU` | 207 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 3 | `ASIN` | 207 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 4 | `MSKU` | 207 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 5 | `Title` | 207 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:179 chars>`, `<redacted:178 chars>`, `<redacted:179 chars>`, `<redacted:182 chars>`, `<redacted:185 chars>` |
| 6 | `Event Type` | 207 | 0 | 1.00 | 6 | `string` | `mapped_candidate` | `Shipments`, `CustomerReturns`, `WhseTransfers`, `Adjustments`, `Receipts` |
| 7 | `Reference ID` | 10 | 197 | 0.05 | 6 | `string` | `mapped_candidate` | `20076865361276`, `FBA197BYW7TJ`, `20077116016028`, `FBA196HC869V`, `20076152691506` |
| 8 | `Quantity` | 207 | 0 | 1.00 | 13 | `integer` | `mapped_candidate` | `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>`, `<redacted:numeric>` |
| 9 | `Fulfillment Center` | 207 | 0 | 1.00 | 96 | `string` | `mapped_candidate` | `PHL7`, `LAS2`, `IND8`, `SLC1`, `MEM3` |
| 10 | `Disposition` | 207 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `SELLABLE`, `DEFECTIVE`, `CUSTOMER_DAMAGED` |
| 11 | `Reason` | 3 | 204 | 0.01 | 2 | `string` | `mapped_candidate` | `E`, `N` |
| 12 | `Country` | 207 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `US` |
| 13 | `Reconciled Quantity` | 3 | 204 | 0.01 | 1 | `integer` | `mapped_candidate` | `<redacted:numeric>` |
| 14 | `Unreconciled Quantity` | 3 | 204 | 0.01 | 1 | `integer` | `mapped_candidate` | `<redacted:numeric>` |
| 15 | `Date and Time` | 207 | 0 | 1.00 | 30 | `datetime_string` | `mapped_candidate` | `2026-05-13T00:00:00-0700`, `2026-05-12T00:00:00-0700`, `2026-05-11T00:00:00-0700`, `2026-05-10T00:00:00-0700`, `2026-05-09T00:00:00-0700` |
| 16 | `Store` | 0 | 207 | 0.00 | 0 | `string` | `mapped_candidate` | - |

## 3. 初步结论

1. 本报告已完成字段统计，但目标 normalized 表仍需人工确认。
2. 原始字段先保留在 raw file 和 `raw_data` 中，避免过早丢失信息。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| 待确认 | `sampling` | 需要结合业务用途和后续样例确认 |
