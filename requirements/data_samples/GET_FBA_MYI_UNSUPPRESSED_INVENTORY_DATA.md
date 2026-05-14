# GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA/2026-05-14/112429020587.txt` |
| encoding | `cp1252` |
| delimiter | `tab` |
| row_count | `5` |
| column_count | `22` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `sku` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 2 | `fnsku` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 3 | `asin` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 4 | `product-name` | 5 | 0 | 1.00 | 5 | `string` | `mapped_candidate` | `<redacted:182 chars>`, `<redacted:179 chars>`, `<redacted:185 chars>`, `<redacted:178 chars>`, `<redacted:179 chars>` |
| 5 | `condition` | 5 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `New` |
| 6 | `your-price` | 5 | 0 | 1.00 | 3 | `decimal` | `mapped_candidate` | `26.00`, `30.99`, `25.00` |
| 7 | `mfn-listing-exists` | 5 | 0 | 1.00 | 1 | `boolean_flag` | `mapped_candidate` | `No` |
| 8 | `mfn-fulfillable-quantity` | 0 | 5 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 9 | `afn-listing-exists` | 5 | 0 | 1.00 | 1 | `boolean_flag` | `mapped_candidate` | `Yes` |
| 10 | `afn-warehouse-quantity` | 5 | 0 | 1.00 | 5 | `integer` | `mapped_candidate` | `284`, `117`, `1`, `226`, `737` |
| 11 | `afn-fulfillable-quantity` | 5 | 0 | 1.00 | 5 | `integer` | `mapped_candidate` | `277`, `114`, `0`, `219`, `731` |
| 12 | `afn-unsellable-quantity` | 5 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `1`, `0` |
| 13 | `afn-reserved-quantity` | 5 | 0 | 1.00 | 4 | `integer` | `mapped_candidate` | `6`, `2`, `1`, `7` |
| 14 | `afn-total-quantity` | 5 | 0 | 1.00 | 5 | `integer` | `mapped_candidate` | `284`, `117`, `1`, `226`, `737` |
| 15 | `per-unit-volume` | 5 | 0 | 1.00 | 3 | `decimal` | `mapped_candidate` | `0.03`, `0.23`, `0.04` |
| 16 | `afn-inbound-working-quantity` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 17 | `afn-inbound-shipped-quantity` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 18 | `afn-inbound-receiving-quantity` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 19 | `afn-researching-quantity` | 5 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `1` |
| 20 | `afn-reserved-future-supply` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 21 | `afn-future-supply-buyable` | 5 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 22 | `store` | 0 | 5 | 0.00 | 0 | `string` | `mapped_candidate` | - |

## 3. 初步结论

1. 本报告适合生成 `amazon_inventory_daily`，用于保存 FBA SKU 库存快照。
2. `afn-fulfillable-quantity` 可作为第一版运营可售库存主口径；`afn-total-quantity`、`afn-reserved-quantity`、`afn-unsellable-quantity` 用于解释库存差异。
3. 本样例的 `mfn-fulfillable-quantity` 与 `store` 为空，但仍应保留字段，避免未来 MFN 或多店铺场景信息丢失。
4. 本报告编码在样例中识别为 cp1252，parser 必须继续使用统一的编码探测逻辑，不要假设所有 Amazon flat file 都是 UTF-8。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_inventory_daily` | `sampling` | 已有真实 FBA 库存样例，可先实现 parser 和字段映射，暂不执行 SQL |
| `amazon_listing_snapshot` | `sampling` | 与 Listing 报告配合，用于补充 title / status / listing id 等信息 |
