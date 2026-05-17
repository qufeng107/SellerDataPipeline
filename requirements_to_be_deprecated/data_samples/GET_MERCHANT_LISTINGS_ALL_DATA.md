# GET_MERCHANT_LISTINGS_ALL_DATA 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_MERCHANT_LISTINGS_ALL_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_MERCHANT_LISTINGS_ALL_DATA/2026-05-13/112285020586.txt` |
| encoding | `utf-8-sig` |
| delimiter | `tab` |
| row_count | `6` |
| column_count | `29` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `item-name` | 6 | 0 | 1.00 | 6 | `string` | `mapped_candidate` | `<redacted:182 chars>`, `<redacted:179 chars>`, `<redacted:178 chars>`, `<redacted:179 chars>`, `<redacted:185 chars>` |
| 2 | `item-description` | 6 | 0 | 1.00 | 2 | `string` | `mapped_candidate` | `<redacted:1333 chars>`, `<redacted:92 chars>` |
| 3 | `listing-id` | 6 | 0 | 1.00 | 6 | `string` | `mapped_candidate` | `<redacted:11 chars>`, `<redacted:11 chars>`, `<redacted:11 chars>`, `<redacted:11 chars>`, `<redacted:11 chars>` |
| 4 | `seller-sku` | 6 | 0 | 1.00 | 6 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 5 | `price` | 5 | 1 | 0.83 | 3 | `decimal` | `mapped_candidate` | `26`, `25`, `30.99` |
| 6 | `quantity` | 0 | 6 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 7 | `open-date` | 6 | 0 | 1.00 | 2 | `datetime_string` | `mapped_candidate` | `2025-11-12 00:11:56 PST`, `2026-01-30 07:07:54 PST` |
| 8 | `image-url` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 9 | `item-is-marketplace` | 6 | 0 | 1.00 | 1 | `boolean_flag` | `mapped_candidate` | `y` |
| 10 | `product-id-type` | 6 | 0 | 1.00 | 1 | `enum_code` | `mapped_candidate` | `1` |
| 11 | `zshop-shipping-fee` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 12 | `item-note` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 13 | `item-condition` | 6 | 0 | 1.00 | 2 | `enum_code` | `mapped_candidate` | `11`, `500` |
| 14 | `zshop-category1` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 15 | `zshop-browse-path` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 16 | `zshop-storefront-feature` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 17 | `asin1` | 6 | 0 | 1.00 | 6 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 18 | `asin2` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 19 | `asin3` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 20 | `will-ship-internationally` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 21 | `expedited-shipping` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 22 | `zshop-boldface` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 23 | `product-id` | 6 | 0 | 1.00 | 6 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 24 | `bid-for-featured-placement` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 25 | `add-delete` | 0 | 6 | 0.00 | 0 | `string` | `deferred` | - |
| 26 | `pending-quantity` | 0 | 6 | 0.00 | 0 | `string` | `mapped_candidate` | - |
| 27 | `fulfillment-channel` | 6 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `AMAZON_NA` |
| 28 | `merchant-shipping-group` | 6 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `Migrated Template` |
| 29 | `status` | 6 | 0 | 1.00 | 3 | `string` | `mapped_candidate` | `Active`, `Inactive`, `Incomplete` |

## 3. 初步结论

1. 本报告适合生成 `amazon_listing_snapshot`，用于维护 SKU / ASIN / Listing / 价格 / 状态等基础信息。
2. FBA 商品在本次样例中 `quantity` 和 `pending-quantity` 为空，因此不应把本报告作为 FBA 可用库存的唯一来源。
3. 长文本、图片、zshop 旧字段等暂缓进入正式列，优先保留在 `raw_data` 和 raw file 中。
4. 后续需要继续取样库存、销售、财务、广告报告，再确认 L3 normalized 表和 L4 reporting 表。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_listing_snapshot` | `sampling` | 已有第一份真实样例，可先实现 parser 和字段映射，暂不执行 SQL |
| `amazon_inventory_daily` | `sampling` | 需要另取 FBA inventory 样例确认真实库存口径 |
