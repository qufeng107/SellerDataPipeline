# GET_SALES_AND_TRAFFIC_REPORT 字段取样记录

> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段统计和脱敏样例。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_SALES_AND_TRAFFIC_REPORT` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_path | `reports/raw/amazon/ATVPDKIKX0DER/GET_SALES_AND_TRAFFIC_REPORT/2026-05-14/112445020587.txt` |
| file_format | `json` |
| encoding | `utf-8-sig` |
| delimiter | `n/a` |
| row_count | `6` |
| field_path_count | `94` |

## 2. 结构备注

- `salesAndTrafficByDate` array length = 6
- `salesAndTrafficByAsin` array length = 1

## 3. 字段统计

| # | source_field_name | non_empty | empty | non_empty_rate | unique | type_suggestion | mapping_status | sample_values |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `reportSpecification.dataEndTime` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `2026-05-14` |
| 2 | `reportSpecification.dataStartTime` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `2026-05-07` |
| 3 | `reportSpecification.marketplaceIds[]` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `ATVPDKIKX0DER` |
| 4 | `reportSpecification.reportOptions.asinGranularity` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `<redacted:6 chars>` |
| 5 | `reportSpecification.reportOptions.dateGranularity` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `DAY` |
| 6 | `reportSpecification.reportType` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `GET_SALES_AND_TRAFFIC_REPORT` |
| 7 | `salesAndTrafficByAsin[].parentAsin` | 1 | 0 | 1.00 | 1 | `string` | `mapped_candidate` | `<redacted:10 chars>` |
| 8 | `salesAndTrafficByAsin[].salesByAsin.orderedProductSales.amount` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 9 | `salesAndTrafficByAsin[].salesByAsin.orderedProductSales.currencyCode` | 1 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `<redacted:3 chars>` |
| 10 | `salesAndTrafficByAsin[].salesByAsin.orderedProductSalesB2B.amount` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:4 chars>` |
| 11 | `salesAndTrafficByAsin[].salesByAsin.orderedProductSalesB2B.currencyCode` | 1 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `<redacted:3 chars>` |
| 12 | `salesAndTrafficByAsin[].salesByAsin.totalOrderItems` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:2 chars>` |
| 13 | `salesAndTrafficByAsin[].salesByAsin.totalOrderItemsB2B` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:1 chars>` |
| 14 | `salesAndTrafficByAsin[].salesByAsin.unitsOrdered` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:2 chars>` |
| 15 | `salesAndTrafficByAsin[].salesByAsin.unitsOrderedB2B` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:1 chars>` |
| 16 | `salesAndTrafficByAsin[].trafficByAsin.browserPageViews` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:3 chars>` |
| 17 | `salesAndTrafficByAsin[].trafficByAsin.browserPageViewsB2B` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:1 chars>` |
| 18 | `salesAndTrafficByAsin[].trafficByAsin.browserPageViewsPercentage` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 19 | `salesAndTrafficByAsin[].trafficByAsin.browserPageViewsPercentageB2B` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 20 | `salesAndTrafficByAsin[].trafficByAsin.browserSessionPercentage` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 21 | `salesAndTrafficByAsin[].trafficByAsin.browserSessionPercentageB2B` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 22 | `salesAndTrafficByAsin[].trafficByAsin.browserSessions` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:3 chars>` |
| 23 | `salesAndTrafficByAsin[].trafficByAsin.browserSessionsB2B` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:1 chars>` |
| 24 | `salesAndTrafficByAsin[].trafficByAsin.buyBoxPercentage` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 25 | `salesAndTrafficByAsin[].trafficByAsin.buyBoxPercentageB2B` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 26 | `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViews` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:3 chars>` |
| 27 | `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsB2B` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:1 chars>` |
| 28 | `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsPercentage` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 29 | `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsPercentageB2B` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:3 chars>` |
| 30 | `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionPercentage` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 31 | `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionPercentageB2B` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:3 chars>` |
| 32 | `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessions` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:3 chars>` |
| 33 | `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionsB2B` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:1 chars>` |
| 34 | `salesAndTrafficByAsin[].trafficByAsin.pageViews` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:3 chars>` |
| 35 | `salesAndTrafficByAsin[].trafficByAsin.pageViewsB2B` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:1 chars>` |
| 36 | `salesAndTrafficByAsin[].trafficByAsin.pageViewsPercentage` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 37 | `salesAndTrafficByAsin[].trafficByAsin.pageViewsPercentageB2B` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 38 | `salesAndTrafficByAsin[].trafficByAsin.sessionPercentage` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 39 | `salesAndTrafficByAsin[].trafficByAsin.sessionPercentageB2B` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:5 chars>` |
| 40 | `salesAndTrafficByAsin[].trafficByAsin.sessions` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:3 chars>` |
| 41 | `salesAndTrafficByAsin[].trafficByAsin.sessionsB2B` | 1 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `<redacted:1 chars>` |
| 42 | `salesAndTrafficByAsin[].trafficByAsin.unitSessionPercentage` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:4 chars>` |
| 43 | `salesAndTrafficByAsin[].trafficByAsin.unitSessionPercentageB2B` | 1 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `<redacted:4 chars>` |
| 44 | `salesAndTrafficByDate[].date` | 6 | 0 | 1.00 | 6 | `datetime_string` | `mapped_candidate` | `2026-05-07`, `2026-05-08`, `2026-05-09`, `2026-05-10`, `2026-05-11` |
| 45 | `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItem.amount` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `25.0`, `25.25` |
| 46 | `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItem.currencyCode` | 6 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 47 | `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItemB2B.amount` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `26.0` |
| 48 | `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItemB2B.currencyCode` | 6 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 49 | `salesAndTrafficByDate[].salesByDate.averageSellingPrice.amount` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `25.0`, `25.25` |
| 50 | `salesAndTrafficByDate[].salesByDate.averageSellingPrice.currencyCode` | 6 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 51 | `salesAndTrafficByDate[].salesByDate.averageSellingPriceB2B.amount` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `26.0` |
| 52 | `salesAndTrafficByDate[].salesByDate.averageSellingPriceB2B.currencyCode` | 6 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 53 | `salesAndTrafficByDate[].salesByDate.averageUnitsPerOrderItem` | 6 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `1.0` |
| 54 | `salesAndTrafficByDate[].salesByDate.averageUnitsPerOrderItemB2B` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `1.0` |
| 55 | `salesAndTrafficByDate[].salesByDate.claimsAmount.amount` | 6 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `0.0` |
| 56 | `salesAndTrafficByDate[].salesByDate.claimsAmount.currencyCode` | 6 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 57 | `salesAndTrafficByDate[].salesByDate.claimsGranted` | 6 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 58 | `salesAndTrafficByDate[].salesByDate.orderedProductSales.amount` | 6 | 0 | 1.00 | 4 | `decimal` | `mapped_candidate` | `100.0`, `50.0`, `75.0`, `101.0` |
| 59 | `salesAndTrafficByDate[].salesByDate.orderedProductSales.currencyCode` | 6 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 60 | `salesAndTrafficByDate[].salesByDate.orderedProductSalesB2B.amount` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `26.0` |
| 61 | `salesAndTrafficByDate[].salesByDate.orderedProductSalesB2B.currencyCode` | 6 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 62 | `salesAndTrafficByDate[].salesByDate.ordersShipped` | 6 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `5`, `1`, `3` |
| 63 | `salesAndTrafficByDate[].salesByDate.refundRate` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `25.0`, `0.0` |
| 64 | `salesAndTrafficByDate[].salesByDate.shippedProductSales.amount` | 6 | 0 | 1.00 | 4 | `decimal` | `mapped_candidate` | `126.0`, `25.0`, `75.0`, `127.0` |
| 65 | `salesAndTrafficByDate[].salesByDate.shippedProductSales.currencyCode` | 6 | 0 | 1.00 | 1 | `currency_code` | `mapped_candidate` | `USD` |
| 66 | `salesAndTrafficByDate[].salesByDate.totalOrderItems` | 6 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `4`, `2`, `3` |
| 67 | `salesAndTrafficByDate[].salesByDate.totalOrderItemsB2B` | 6 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `1` |
| 68 | `salesAndTrafficByDate[].salesByDate.unitsOrdered` | 6 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `4`, `2`, `3` |
| 69 | `salesAndTrafficByDate[].salesByDate.unitsOrderedB2B` | 6 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `0`, `1` |
| 70 | `salesAndTrafficByDate[].salesByDate.unitsRefunded` | 6 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `1`, `0` |
| 71 | `salesAndTrafficByDate[].salesByDate.unitsShipped` | 6 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `5`, `1`, `3` |
| 72 | `salesAndTrafficByDate[].trafficByDate.averageOfferCount` | 6 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `4` |
| 73 | `salesAndTrafficByDate[].trafficByDate.averageParentItems` | 6 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `1` |
| 74 | `salesAndTrafficByDate[].trafficByDate.browserPageViews` | 6 | 0 | 1.00 | 6 | `integer` | `mapped_candidate` | `28`, `20`, `31`, `19`, `37` |
| 75 | `salesAndTrafficByDate[].trafficByDate.browserPageViewsB2B` | 6 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `2`, `0`, `3` |
| 76 | `salesAndTrafficByDate[].trafficByDate.browserSessions` | 6 | 0 | 1.00 | 6 | `integer` | `mapped_candidate` | `20`, `19`, `25`, `15`, `30` |
| 77 | `salesAndTrafficByDate[].trafficByDate.browserSessionsB2B` | 6 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `2`, `0`, `3` |
| 78 | `salesAndTrafficByDate[].trafficByDate.buyBoxPercentage` | 6 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `100.0` |
| 79 | `salesAndTrafficByDate[].trafficByDate.buyBoxPercentageB2B` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `100.0` |
| 80 | `salesAndTrafficByDate[].trafficByDate.feedbackReceived` | 6 | 0 | 1.00 | 2 | `integer` | `mapped_candidate` | `1`, `0` |
| 81 | `salesAndTrafficByDate[].trafficByDate.mobileAppPageViews` | 6 | 0 | 1.00 | 6 | `integer` | `mapped_candidate` | `48`, `59`, `58`, `65`, `50` |
| 82 | `salesAndTrafficByDate[].trafficByDate.mobileAppPageViewsB2B` | 6 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 83 | `salesAndTrafficByDate[].trafficByDate.mobileAppSessions` | 6 | 0 | 1.00 | 6 | `integer` | `mapped_candidate` | `32`, `34`, `39`, `44`, `31` |
| 84 | `salesAndTrafficByDate[].trafficByDate.mobileAppSessionsB2B` | 6 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 85 | `salesAndTrafficByDate[].trafficByDate.negativeFeedbackReceived` | 6 | 0 | 1.00 | 1 | `integer` | `mapped_candidate` | `0` |
| 86 | `salesAndTrafficByDate[].trafficByDate.orderItemSessionPercentage` | 6 | 0 | 1.00 | 6 | `decimal` | `mapped_candidate` | `7.69`, `3.77`, `4.69`, `3.39`, `6.56` |
| 87 | `salesAndTrafficByDate[].trafficByDate.orderItemSessionPercentageB2B` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `33.33` |
| 88 | `salesAndTrafficByDate[].trafficByDate.pageViews` | 6 | 0 | 1.00 | 6 | `integer` | `mapped_candidate` | `76`, `79`, `89`, `84`, `87` |
| 89 | `salesAndTrafficByDate[].trafficByDate.pageViewsB2B` | 6 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `2`, `0`, `3` |
| 90 | `salesAndTrafficByDate[].trafficByDate.receivedNegativeFeedbackRate` | 6 | 0 | 1.00 | 1 | `decimal` | `mapped_candidate` | `0.0` |
| 91 | `salesAndTrafficByDate[].trafficByDate.sessions` | 6 | 0 | 1.00 | 6 | `integer` | `mapped_candidate` | `52`, `53`, `64`, `59`, `61` |
| 92 | `salesAndTrafficByDate[].trafficByDate.sessionsB2B` | 6 | 0 | 1.00 | 3 | `integer` | `mapped_candidate` | `2`, `0`, `3` |
| 93 | `salesAndTrafficByDate[].trafficByDate.unitSessionPercentage` | 6 | 0 | 1.00 | 6 | `decimal` | `mapped_candidate` | `7.69`, `3.77`, `4.69`, `3.39`, `6.56` |
| 94 | `salesAndTrafficByDate[].trafficByDate.unitSessionPercentageB2B` | 6 | 0 | 1.00 | 2 | `decimal` | `mapped_candidate` | `0.0`, `33.33` |

## 4. 初步结论

1. 本报告是 JSON 格式，不是 tab-delimited flat file；字段以 JSON path 方式记录。
2. 本次样例包含 `salesAndTrafficByDate` 6 行；本次样例包含 `salesAndTrafficByAsin` 1 行，可开始确认 ASIN 维度字段。
3. 日期维度适合生成 `amazon_sales_traffic_daily`，用于销售额、订单、退款、session、page view、转化率等运营指标。
4. ASIN 维度适合生成 `amazon_sales_traffic_asin_daily`，当前样例为 PARENT 粒度，后续可再测试 CHILD 粒度是否需要。

## 5. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_sales_traffic_daily` | `sampling` | 已有日期维度真实样例，可实现 parser 和字段映射，暂不执行 SQL |
| `amazon_sales_traffic_asin_daily` | `sampling` | 已有 ASIN 维度样例时，可进入 parser 和字段映射；暂不执行 SQL |
