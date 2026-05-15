# spPurchasedProduct 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `amazon_ads` |
| report_type | `spPurchasedProduct` |
| marketplace_id | `3917953989967300` |
| raw_file_path | `reports\raw\amazon_ads\3917953989967300\spPurchasedProduct\2026-05-15\7ee85e28-5800-4095-8f7f-d111e70445c1.json` |
| file_format | `json` |
| encoding | `utf-8-sig` |
| delimiter | `n/a` |
| row_count | `0` |
| field_path_count | `1` |

## 2. 结构备注

- top-level array length = 0

## 3. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `[]` | 0 | 0 | 0.00 | 0 | `string` | `deferred` | - |

## 4. 初步结论

1. 本报告已通过真实 Amazon Ads API canary 提交和下载，但当前 3 天窗口返回空数组，说明本窗口没有可观测的 purchased product 归因行；这不是 API 或 parser 失败。
2. Ads API 是广告运营归因口径，适合解释 campaign、关键词、搜索词或 ASIN 维度表现；利润核算中的广告真实扣费仍优先以 Settlement V2 为财务口径。
3. 本报告第一版 parser 采用通用 Ads normalized row，正式入库前再按 reportTypeId 拆到目标明细表。

## 5. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_ads_sp_purchased_product_daily` | `sampling_confirmed_empty` | Purchased ASIN attribution after ad clicks for halo-sales analysis. 暂不执行 SQL |
