# GET_LEDGER_SUMMARY_VIEW_DATA 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_LEDGER_SUMMARY_VIEW_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_LEDGER_SUMMARY_VIEW_DATA/2026-05-14/112473020587.txt` |
| file_format | `delimited` |
| encoding | `utf-8-sig` |
| delimiter | `tab` |
| row_count | `150` |
| field_path_count | `22` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `Date` | 150 | 0 | 1.00 | 30 | `datetime_string` | `mapped_candidate` | `05/13/2026`, `05/12/2026`, `05/11/2026`, `05/10/2026`, `05/09/2026` |
| 2 | `FNSKU` | 150 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 3 | `ASIN` | 150 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 4 | `MSKU` | 150 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 5 | `Title` | 150 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:185 chars>`, `<redacted:179 chars>`, `<redacted:182 chars>`, `<redacted:178 chars>`, `<redacted:179 chars>` |
| 6 | `Disposition` | 150 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `SELLABLE`, `DEFECTIVE`, `CUSTOMER_DAMAGED` |
| 7 | `Starting Warehouse Balance` | 150 | 0 | 1.00 | 48 | `integer` | `mapped_candidate` | `1`, `118`, `283`, `226`, `740` |
| 8 | `In Transit Between Warehouses` | 150 | 0 | 1.00 | 10 | `integer` | `mapped_candidate` | `0`, `2`, `1`, `3`, `4` |
| 9 | `Receipts` | 150 | 0 | 1.00 | 6 | `integer` | `mapped_candidate` | `0`, `1`, `6`, `-6`, `4` |
| 10 | `Customer Shipments` | 150 | 0 | 1.00 | 7 | `integer` | `mapped_candidate` | `0`, `-1`, `-2`, `-3`, `-4` |
| 11 | `Customer Returns` | 150 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `0`, `1`, `2` |
| 12 | `Vendor Returns` | 150 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `-1` |
| 13 | `Warehouse Transfer In/Out` | 150 | 0 | 1.00 | 11 | `integer` | `mapped_candidate` | `0`, `-1`, `1`, `2`, `-3` |
| 14 | `Found` | 150 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `1` |
| 15 | `Lost` | 150 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 16 | `Damaged` | 150 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 17 | `Disposed` | 150 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 18 | `Other Events` | 150 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `-1` |
| 19 | `Ending Warehouse Balance` | 150 | 0 | 1.00 | 47 | `integer` | `mapped_candidate` | `1`, `118`, `283`, `226`, `739` |
| 20 | `Unknown Events` | 150 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 21 | `Location` | 150 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `US` |
| 22 | `Store` | 0 | 150 | 0.00 | 0 | `string` | `mapped_candidate` | - |

## 3. 初步结论

1. 本报告适合生成 `amazon_inventory_ledger_summary_daily`，用于库存流水汇总、丢失/损坏/找到/退货/发货等 movement 对账。
2. 当前样例是 COUNTRY + DAILY 粒度；若后续需要仓库维度，可再请求 aggregateByLocation=FC。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_inventory_ledger_summary_daily` | `sampling` | 已有真实样例，暂不执行 SQL |
