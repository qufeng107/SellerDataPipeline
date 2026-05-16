# GET_FBA_INVENTORY_PLANNING_DATA 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_FBA_INVENTORY_PLANNING_DATA` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_FBA_INVENTORY_PLANNING_DATA/2026-05-14/112472020587.txt` |
| file_format | `delimited` |
| encoding | `utf-8-sig` |
| delimiter | `tab` |
| row_count | `4` |
| field_path_count | `97` |

## 2. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `snapshot-date` | 4 | 0 | 1.00 | 1 | `datetime_string` | `mapped_candidate` | `2026-05-14` |
| 2 | `sku` | 4 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>`, `<redacted:12 chars>` |
| 3 | `fnsku` | 4 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 4 | `asin` | 4 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>`, `<redacted:10 chars>` |
| 5 | `product-name` | 4 | 0 | 1.00 | 4 | `string` | `mapped_candidate` | `<redacted:178 chars>`, `<redacted:179 chars>`, `<redacted:179 chars>`, `<redacted:182 chars>` |
| 6 | `condition` | 4 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `New` |
| 7 | `available` | 4 | 0 | 1.00 | 4 | `integer` | `mapped_candidate` | `219`, `114`, `731`, `277` |
| 8 | `pending-removal-quantity` | 4 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 9 | `inv-age-0-to-90-days` | 4 | 0 | 1.00 | 4 | `integer` | `mapped_candidate` | `8`, `28`, `730`, `6` |
| 10 | `inv-age-91-to-180-days` | 4 | 0 | 1.00 | 4 | `integer` | `mapped_candidate` | `212`, `88`, `0`, `272` |
| 11 | `inv-age-181-to-270-days` | 4 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 12 | `inv-age-271-to-365-days` | 4 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 13 | `inv-age-366-to-455-days` | 4 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 14 | `inv-age-456-plus-days` | 4 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 15 | `currency` | 4 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 16 | `units-shipped-t7` | 4 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `3`, `15`, `0` |
| 17 | `units-shipped-t30` | 4 | 0 | 1.00 | 4 | `integer` | `mapped_candidate` | `12`, `17`, `82`, `3` |
| 18 | `units-shipped-t60` | 4 | 0 | 1.00 | 4 | `integer` | `mapped_candidate` | `52`, `65`, `284`, `26` |
| 19 | `units-shipped-t90` | 4 | 0 | 1.00 | 4 | `integer` | `mapped_candidate` | `96`, `142`, `487`, `66` |
| 20 | `alert` | 4 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `Low traffic` |
| 21 | `your-price` | 4 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `25.0`, `26.0` |
| 22 | `sales-price` | 4 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `0.0` |
| 23 | `lowest-price-new-plus-shipping` | 4 | 0 | 1.00 | 2 | `decimal` | `deferred` | `25.0`, `26.0` |
| 24 | `lowest-price-used` | 4 | 0 | 1.00 | 2 | `decimal` | `deferred` | `0.0`, `21.96` |
| 25 | `recommended-action` | 4 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `NoExcessInventory` |
| 26 | `DEPRECATED healthy-inventory-level` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 27 | `recommended-sales-price` | 4 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `0.0` |
| 28 | `recommended-sale-duration-days` | 4 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 29 | `recommended-removal-quantity` | 4 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 30 | `estimated-cost-savings-of-recommended-actions` | 4 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `0.0` |
| 31 | `sell-through` | 4 | 0 | 1.00 | 4 | `decimal` | `mapped_candidate` | `0.36`, `0.87`, `0.91`, `0.22` |
| 32 | `item-volume` | 4 | 0 | 1.00 | 4 | `decimal` | `mapped_candidate` | `0.031883`, `0.026657`, `0.035646`, `0.031516` |
| 33 | `volume-unit-measurement` | 4 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `cubic feet` |
| 34 | `storage-type` | 4 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `Standard` |
| 35 | `storage-volume` | 4 | 0 | 1.00 | 4 | `decimal` | `mapped_candidate` | `6.982377`, `3.038898`, `26.057226`, `8.729932` |
| 36 | `marketplace` | 4 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `US` |
| 37 | `product-group` | 4 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `gl_luggage` |
| 38 | `sales-rank` | 4 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `262703` |
| 39 | `days-of-supply` | 4 | 0 | 1.00 | 4 | `integer` | `mapped_candidate` | `274`, `179`, `207`, `366` |
| 40 | `estimated-excess-quantity` | 4 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 41 | `weeks-of-cover-t30` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `73`, `26`, `35`, `369` |
| 42 | `weeks-of-cover-t90` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `29`, `10`, `19`, `54` |
| 43 | `featuredoffer-price` | 4 | 0 | 1.00 | 2 | `decimal` | `deferred` | `25.0`, `26.0` |
| 44 | `sales-shipped-last-7-days` | 4 | 0 | 1.00 | 4 | `decimal` | `deferred` | `75.0`, `78.0`, `375.0`, `0.0` |
| 45 | `sales-shipped-last-30-days` | 4 | 0 | 1.00 | 4 | `decimal` | `deferred` | `285.0`, `442.0`, `1940.0`, `75.4` |
| 46 | `sales-shipped-last-60-days` | 4 | 0 | 1.00 | 4 | `decimal` | `deferred` | `1285.0`, `1657.5`, `6321.12`, `645.28` |
| 47 | `sales-shipped-last-90-days` | 4 | 0 | 1.00 | 4 | `decimal` | `deferred` | `2216.25`, `3295.5`, `10396.9`, `1460.64` |
| 48 | `inv-age-0-to-30-days` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `0`, `3`, `21`, `2` |
| 49 | `inv-age-31-to-60-days` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `5`, `12`, `619`, `2` |
| 50 | `inv-age-61-to-90-days` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `3`, `13`, `90`, `2` |
| 51 | `inv-age-181-to-330-days` | 4 | 0 | 1.00 | 1 | `integer` | `deferred` | `0` |
| 52 | `inv-age-331-to-365-days` | 4 | 0 | 1.00 | 1 | `integer` | `deferred` | `0` |
| 53 | `estimated-storage-cost-next-month` | 4 | 0 | 1.00 | 4 | `decimal` | `deferred` | `4.73`, `1.83`, `16.69`, `6.03` |
| 54 | `inbound-quantity` | 4 | 0 | 1.00 | 1 | `integer` | `deferred` | `0` |
| 55 | `inbound-working` | 4 | 0 | 1.00 | 1 | `integer` | `deferred` | `0` |
| 56 | `inbound-shipped` | 4 | 0 | 1.00 | 1 | `integer` | `deferred` | `0` |
| 57 | `inbound-received` | 4 | 0 | 1.00 | 1 | `integer` | `deferred` | `0` |
| 58 | `no-sale-last-6-months` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 59 | `Total Reserved Quantity` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `7`, `3`, `10`, `6` |
| 60 | `unfulfillable-quantity` | 4 | 0 | 1.00 | 1 | `integer` | `deferred` | `0` |
| 61 | `quantity-to-be-charged-ais-181-210-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 62 | `estimated-ais-181-210-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 63 | `quantity-to-be-charged-ais-211-240-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 64 | `estimated-ais-211-240-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 65 | `quantity-to-be-charged-ais-241-270-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 66 | `estimated-ais-241-270-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 67 | `quantity-to-be-charged-ais-271-300-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 68 | `estimated-ais-271-300-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 69 | `quantity-to-be-charged-ais-301-330-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 70 | `estimated-ais-301-330-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 71 | `quantity-to-be-charged-ais-331-365-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 72 | `estimated-ais-331-365-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 73 | `quantity-to-be-charged-ais-366-455-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 74 | `estimated-ais-366-455-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 75 | `quantity-to-be-charged-ais-456-plus-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 76 | `estimated-ais-456-plus-days` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 77 | `historical-days-of-supply` | 4 | 0 | 1.00 | 4 | `decimal` | `deferred` | `584.8`, `167.8`, `253.0`, `2128.5` |
| 78 | `fba-minimum-inventory-level` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `35`, `39`, `195`, `19` |
| 79 | `fba-inventory-level-health-status` | 4 | 0 | 1.00 | 1 | `string` | `deferred` | `Healthy` |
| 80 | `Recommended ship-in quantity` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 81 | `Recommended ship-in date` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 82 | `Last updated date for Historical Days of Supply` | 4 | 0 | 1.00 | 1 | `datetime_string` | `deferred` | `2026-05-11` |
| 83 | `Exempted from Low-Inventory-Level fee?` | 4 | 0 | 1.00 | 1 | `boolean_flag` | `deferred` | `Yes` |
| 84 | `Low-Inventory-Level fee applied in current week?` | 4 | 0 | 1.00 | 1 | `boolean_flag` | `deferred` | `No` |
| 85 | `Short term historical days of supply` | 4 | 0 | 1.00 | 4 | `decimal` | `deferred` | `584.8`, `167.8`, `253.0`, `2128.5` |
| 86 | `Long term historical days of supply` | 4 | 0 | 1.00 | 4 | `decimal` | `deferred` | `233.3`, `93.7`, `99.8`, `406.6` |
| 87 | `Inventory age snapshot date` | 4 | 0 | 1.00 | 1 | `datetime_string` | `deferred` | `2026-05-11` |
| 88 | `Inventory Supply at FBA` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `219`, `115`, `735`, `277` |
| 89 | `Reserved FC Transfer` | 4 | 0 | 1.00 | 3 | `integer` | `deferred` | `0`, `1`, `4` |
| 90 | `Reserved FC Processing` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `7`, `2`, `5`, `6` |
| 91 | `Reserved Customer Order` | 4 | 0 | 1.00 | 2 | `integer` | `deferred` | `0`, `1` |
| 92 | `Total Days of Supply (including units from open shipments)` | 4 | 0 | 1.00 | 4 | `integer` | `deferred` | `285`, `181`, `208`, `366` |
| 93 | `supplier` | 4 | 0 | 1.00 | 1 | `string` | `deferred` | `unassigned` |
| 94 | `is-seasonal-in-next-3-months` | 4 | 0 | 1.00 | 1 | `boolean_flag` | `deferred` | `N` |
| 95 | `season-name` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 96 | `season-start-date` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |
| 97 | `season-end-date` | 0 | 4 | 0.00 | 0 | `string` | `deferred` | - |

## 3. 初步结论

1. 本报告适合生成 `amazon_inventory_planning_daily`，用于库存健康、库龄、周转、冗余和建议动作。
2. 字段较多且部分字段在样例为空，第一版正式列应优先保留 available、库龄、units shipped、days of supply、excess quantity。

## 4. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_inventory_planning_daily` | `sampling` | 已有真实样例，暂不执行 SQL |
