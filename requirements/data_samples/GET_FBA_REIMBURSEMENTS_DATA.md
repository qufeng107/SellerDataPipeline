# GET_FBA_REIMBURSEMENTS_DATA 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_FBA_REIMBURSEMENTS_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FBA_REIMBURSEMENTS_DATA/2026-05-14/112469020587.txt` |
| file_format | `delimited` |
| encoding | `cp1252` |
| delimiter | `tab` |
| row_count | `19` |
| field_path_count | `18` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `approval-date` | 19 | 0 | 1.00 | 19 | `datetime_string` | `mapped_candidate` | `2026-05-12T09:59:13+00:00`, `2026-05-11T20:18:41+00:00`, `2026-05-11T11:17:34+00:00`, `2026-04-29T22:44:07+00:00`, `2026-04-28T07:01:59+00:00` |
| 2 | `reimbursement-id` | 19 | 0 | 1.00 | 19 | `integer` | `mapped_candidate` | `<redacted:11 chars>`, `<redacted:11 chars>`, `<redacted:11 chars>`, `<redacted:11 chars>`, `<redacted:11 chars>` |
| 3 | `case-id` | 0 | 19 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 4 | `amazon-order-id` | 13 | 6 | 0.68 | 12 | `string` | `mapped_candidate` | `<redacted:19 chars>`, `<redacted:19 chars>`, `<redacted:19 chars>`, `<redacted:19 chars>`, `<redacted:19 chars>` |
| 5 | `reason` | 19 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `CustomerReturn`, `Damaged_Warehouse`, `Reimbursement_Reversal`, `CustomerServiceIssue` |
| 6 | `sku` | 19 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 7 | `fnsku` | 19 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 8 | `asin` | 19 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 9 | `product-name` | 19 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `<redacted:179 chars>`, `<redacted:185 chars>`, `<redacted:179 chars>` |
| 10 | `condition` | 19 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `NewItem` |
| 11 | `currency-unit` | 19 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `USD` |
| 12 | `amount-per-unit` | 19 | 0 | 1.00 | 13 | `decimal` | `mapped_candidate` | `15.45`, `7.20`, `12.10`, `-6.38`, `16.85` |
| 13 | `amount-total` | 19 | 0 | 1.00 | 14 | `decimal` | `mapped_candidate` | `15.45`, `7.20`, `12.10`, `-6.38`, `16.85` |
| 14 | `quantity-reimbursed-cash` | 19 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `1`, `-1`, `-2` |
| 15 | `quantity-reimbursed-inventory` | 19 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `0`, `1`, `2` |
| 16 | `quantity-reimbursed-total` | 19 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `1`, `0` |
| 17 | `original-reimbursement-id` | 4 | 15 | 0.21 | 3 | `integer` | `mapped_candidate` | `<redacted:11 chars>`, `<redacted:11 chars>`, `<redacted:11 chars>` |
| 18 | `original-reimbursement-type` | 4 | 15 | 0.21 | 3 | `string` | `mapped_candidate` | `Lost_Warehouse`, `CustomerReturn`, `Damaged_Warehouse` |

## 3. 初步结论

1. 本报告适合生成 `amazon_fba_reimbursement`，用于赔偿、赔库存、赔现金和原始 reimbursement id 追踪。
2. 样例中 `reason` 可作为赔偿分类初始口径，后续再与 settlement 中 reimbursement 事件对账。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_fba_reimbursement` | `sampling` | 已有真实样例，暂不执行 SQL |
