# GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE/2026-05-14/112468020587.txt` |
| file_format | `delimited` |
| encoding | `utf-8-sig` |
| delimiter | `tab` |
| row_count | `0` |
| field_path_count | `33` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `Order ID` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 2 | `Order date` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 3 | `Return request date` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 4 | `Return request status` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 5 | `Amazon RMA ID` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 6 | `Merchant RMA ID` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 7 | `Label type` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 8 | `Label cost` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 9 | `Currency code` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 10 | `Return carrier` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 11 | `Tracking ID` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 12 | `Label to be paid by` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 13 | `A-to-Z Claim` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 14 | `Is prime` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 15 | `ASIN` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 16 | `Merchant SKU` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 17 | `Item Name` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 18 | `Return quantity` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 19 | `Return Reason` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 20 | `In policy` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 21 | `Return type` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 22 | `Resolution` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 23 | `Invoice number` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 24 | `Return delivery date` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 25 | `Order Amount` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 26 | `Order quantity` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 27 | `SafeT Action reason` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 28 | `SafeT claim id` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 29 | `SafeT claim state` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 30 | `SafeT claim creation time` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 31 | `SafeT claim reimbursement amount` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 32 | `Refunded Amount` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 33 | `Order Item ID` | 0 | 0 | 0.00 | 0 | `string` | `mapped_candidate` | - |

## 3. 初步结论

1. 本次返回 header-only，说明当前窗口无可用退货行，但字段结构已经可用于 parser 和表设计。
2. 本报告适合生成 `amazon_return_request`，用于 RMA、退货原因、退货状态、Safe-T 和退款金额分析。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_return_request` | `sampling` | 已有字段结构，仍需补含数据行样例 |
