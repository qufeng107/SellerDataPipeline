# SP-API Reports 数据接入目录

> 更新时间：2026-05-16  
> 文档定位：记录本项目通过 Amazon SP-API Reports 可以接入的 report type、获取方式、样例格式和已观察字段。本文只描述数据接入能力，不定义业务功能和数据库设计。

## 1. 获取方式

常规 SP-API Reports 流程：

```text
createReport
  -> getReports / getReport
  -> getReportDocument
  -> download/decrypt/decompress raw report
  -> save to reports/raw/amazon/{marketplace_id}/{report_type}/{date}/...
```

特殊情况：

- `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` 是 Amazon 自动生成的 settlement report，当前通过 `getReports` discovery 下载，不通过普通 `createReport` 主动创建。
- `GET_PROMOTION_PERFORMANCE_REPORT` 需要 `promotionStartDateFrom` / `promotionStartDateTo` reportOptions。
- `GET_COUPON_PERFORMANCE_REPORT` 需要 `couponStartDateFrom` / `couponStartDateTo` reportOptions。
- 部分 FBA 费用、库存异常、移除建议类报告可能在当前账号或当前窗口返回 cancelled/no-data；这不等于接口不可用。

## 2. 默认敏感数据规则

默认取样计划不请求可能包含买家联系方式、地址或客户评论的报告。需要显式 `--include-sensitive` 才考虑请求。

当前默认排除：

| report_type | 原因 |
|---|---|
| `GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL` | 可能包含买家/contact/address 相关字段。 |
| `GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA` | 可能包含 customer comments。 |

即便本地下载，也只能提交脱敏字段记录，不能提交真实 raw file。

## 3. 当前已取样并分析的 SP-API Reports

### GET_COUPON_PERFORMANCE_REPORT

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport with couponStartDateFrom / couponStartDateTo reportOptions |
| Current sample file | `requirements/data_samples/GET_COUPON_PERFORMANCE_REPORT.md` |
| Format | `json` |
| Delimiter | `n/a` |
| Current sample rows | `2` |
| Observed field/path count | `23` |
| Status | `sampled + analyzed` |
| Data domain | Coupon performance |

Observed source fields:

`coupons[].asins[].asin`, `coupons[].budget`, `coupons[].budgetPercentageUsed`, `coupons[].budgetRemaining`, `coupons[].budgetSpent`, `coupons[].clips`, `coupons[].couponId`, `coupons[].currencyCode`, `coupons[].discountAmount`, `coupons[].discountType`, `coupons[].endDateTime`, `coupons[].marketplaceId`, `coupons[].merchantId`, `coupons[].name`, `coupons[].redemptions`, `coupons[].sales`, `coupons[].startDateTime`, `coupons[].totalDiscount`, `coupons[].websiteMessage`, `reportSpecification.marketplaceIds[]`, `reportSpecification.reportOptions.couponStartDateFrom`, `reportSpecification.reportOptions.couponStartDateTo`, `reportSpecification.reportType`

Notes:

- Diagnostic sampling confirmed required date reportOptions; current sample with options is available.

### GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `8` |
| Observed field/path count | `31` |
| Status | `sampled + analyzed` |
| Data domain | FBA estimated fee preview |

Observed source fields:

`sku`, `fnsku`, `asin`, `amazon-store`, `product-name`, `product-group`, `brand`, `fulfilled-by`, `your-price`, `sales-price`, `longest-side`, `median-side`, `shortest-side`, `length-and-girth`, `unit-of-dimension`, `item-package-weight`, `unit-of-weight`, `product-size-tier`, `currency`, `estimated-fee-total`, `estimated-referral-fee-per-unit`, `estimated-variable-closing-fee`, `estimated-order-handling-fee-per-order`, `estimated-pick-pack-fee-per-unit`, `estimated-weight-handling-fee-per-unit`, `expected-fulfillment-fee-per-unit`, `estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)`, `estimated-future-order-handling-fee-per-order`, `estimated-future-pick-pack-fee-per-unit`, `estimated-future-weight-handling-fee-per-unit`, `expected-future-fulfillment-fee-per-unit`

### GET_FBA_INVENTORY_PLANNING_DATA

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_FBA_INVENTORY_PLANNING_DATA.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `4` |
| Observed field/path count | `97` |
| Status | `sampled + analyzed` |
| Data domain | FBA inventory planning / inventory health |

Observed source fields:

`snapshot-date`, `sku`, `fnsku`, `asin`, `product-name`, `condition`, `available`, `pending-removal-quantity`, `inv-age-0-to-90-days`, `inv-age-91-to-180-days`, `inv-age-181-to-270-days`, `inv-age-271-to-365-days`, `inv-age-366-to-455-days`, `inv-age-456-plus-days`, `currency`, `units-shipped-t7`, `units-shipped-t30`, `units-shipped-t60`, `units-shipped-t90`, `alert`, `your-price`, `sales-price`, `lowest-price-new-plus-shipping`, `lowest-price-used`, `recommended-action`, `DEPRECATED healthy-inventory-level`, `recommended-sales-price`, `recommended-sale-duration-days`, `recommended-removal-quantity`, `estimated-cost-savings-of-recommended-actions`, `sell-through`, `item-volume`, `volume-unit-measurement`, `storage-type`, `storage-volume`, `marketplace`, `product-group`, `sales-rank`, `days-of-supply`, `estimated-excess-quantity`, `weeks-of-cover-t30`, `weeks-of-cover-t90`, `featuredoffer-price`, `sales-shipped-last-7-days`, `sales-shipped-last-30-days`, `sales-shipped-last-60-days`, `sales-shipped-last-90-days`, `inv-age-0-to-30-days`, `inv-age-31-to-60-days`, `inv-age-61-to-90-days`, `inv-age-181-to-330-days`, `inv-age-331-to-365-days`, `estimated-storage-cost-next-month`, `inbound-quantity`, `inbound-working`, `inbound-shipped`, `inbound-received`, `no-sale-last-6-months`, `Total Reserved Quantity`, `unfulfillable-quantity`, `quantity-to-be-charged-ais-181-210-days`, `estimated-ais-181-210-days`, `quantity-to-be-charged-ais-211-240-days`, `estimated-ais-211-240-days`, `quantity-to-be-charged-ais-241-270-days`, `estimated-ais-241-270-days`, `quantity-to-be-charged-ais-271-300-days`, `estimated-ais-271-300-days`, `quantity-to-be-charged-ais-301-330-days`, `estimated-ais-301-330-days`, `quantity-to-be-charged-ais-331-365-days`, `estimated-ais-331-365-days`, `quantity-to-be-charged-ais-366-455-days`, `estimated-ais-366-455-days`, `quantity-to-be-charged-ais-456-plus-days`, `estimated-ais-456-plus-days`, `historical-days-of-supply`, `fba-minimum-inventory-level`, `fba-inventory-level-health-status`, `Recommended ship-in quantity`, `Recommended ship-in date`, `Last updated date for Historical Days of Supply`, `Exempted from Low-Inventory-Level fee?`, `Low-Inventory-Level fee applied in current week?`, `Short term historical days of supply`, `Long term historical days of supply`, `Inventory age snapshot date`, `Inventory Supply at FBA`, `Reserved FC Transfer`, `Reserved FC Processing`, `Reserved Customer Order`, `Total Days of Supply (including units from open shipments)`, `supplier`, `is-seasonal-in-next-3-months`, `season-name`, `season-start-date`, `season-end-date`

### GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `5` |
| Observed field/path count | `22` |
| Status | `sampled + analyzed` |
| Data domain | FBA inventory availability and quantity snapshot |

Observed source fields:

`sku`, `fnsku`, `asin`, `product-name`, `condition`, `your-price`, `mfn-listing-exists`, `mfn-fulfillable-quantity`, `afn-listing-exists`, `afn-warehouse-quantity`, `afn-fulfillable-quantity`, `afn-unsellable-quantity`, `afn-reserved-quantity`, `afn-total-quantity`, `per-unit-volume`, `afn-inbound-working-quantity`, `afn-inbound-shipped-quantity`, `afn-inbound-receiving-quantity`, `afn-researching-quantity`, `afn-reserved-future-supply`, `afn-future-supply-buyable`, `store`

### GET_FBA_REIMBURSEMENTS_DATA

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_FBA_REIMBURSEMENTS_DATA.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `19` |
| Observed field/path count | `18` |
| Status | `sampled + analyzed` |
| Data domain | FBA reimbursement report |

Observed source fields:

`approval-date`, `reimbursement-id`, `case-id`, `amazon-order-id`, `reason`, `sku`, `fnsku`, `asin`, `product-name`, `condition`, `currency-unit`, `amount-per-unit`, `amount-total`, `quantity-reimbursed-cash`, `quantity-reimbursed-inventory`, `quantity-reimbursed-total`, `original-reimbursement-id`, `original-reimbursement-type`

### GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `112` |
| Observed field/path count | `33` |
| Status | `sampled + analyzed` |
| Data domain | Order-item level order report by order date |

Observed source fields:

`amazon-order-id`, `merchant-order-id`, `purchase-date`, `last-updated-date`, `order-status`, `fulfillment-channel`, `sales-channel`, `order-channel`, `ship-service-level`, `product-name`, `sku`, `asin`, `item-status`, `quantity`, `currency`, `item-price`, `item-tax`, `shipping-price`, `shipping-tax`, `gift-wrap-price`, `gift-wrap-tax`, `item-promotion-discount`, `ship-promotion-discount`, `ship-city`, `ship-state`, `ship-postal-code`, `ship-country`, `promotion-ids`, `cpf`, `is-business-order`, `purchase-order-number`, `price-designation`, `signature-confirmation-recommended`

### GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `0` |
| Observed field/path count | `33` |
| Status | `sampled header-only / empty` |
| Data domain | Return request report by return date |

Observed source fields:

`Order ID`, `Order date`, `Return request date`, `Return request status`, `Amazon RMA ID`, `Merchant RMA ID`, `Label type`, `Label cost`, `Currency code`, `Return carrier`, `Tracking ID`, `Label to be paid by`, `A-to-Z Claim`, `Is prime`, `ASIN`, `Merchant SKU`, `Item Name`, `Return quantity`, `Return Reason`, `In policy`, `Return type`, `Resolution`, `Invoice number`, `Return delivery date`, `Order Amount`, `Order quantity`, `SafeT Action reason`, `SafeT claim id`, `SafeT claim state`, `SafeT claim creation time`, `SafeT claim reimbursement amount`, `Refunded Amount`, `Order Item ID`

### GET_LEDGER_DETAIL_VIEW_DATA

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_LEDGER_DETAIL_VIEW_DATA.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `207` |
| Observed field/path count | `16` |
| Status | `sampled + analyzed` |
| Data domain | Inventory ledger detail events |

Observed source fields:

`Date`, `FNSKU`, `ASIN`, `MSKU`, `Title`, `Event Type`, `Reference ID`, `Quantity`, `Fulfillment Center`, `Disposition`, `Reason`, `Country`, `Reconciled Quantity`, `Unreconciled Quantity`, `Date and Time`, `Store`

### GET_LEDGER_SUMMARY_VIEW_DATA

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport with reportOptions aggregateByLocation=COUNTRY, aggregatedByTimePeriod=DAILY in current plan |
| Current sample file | `requirements/data_samples/GET_LEDGER_SUMMARY_VIEW_DATA.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `150` |
| Observed field/path count | `22` |
| Status | `sampled + analyzed` |
| Data domain | Inventory ledger summary |

Observed source fields:

`Date`, `FNSKU`, `ASIN`, `MSKU`, `Title`, `Disposition`, `Starting Warehouse Balance`, `In Transit Between Warehouses`, `Receipts`, `Customer Shipments`, `Customer Returns`, `Vendor Returns`, `Warehouse Transfer In/Out`, `Found`, `Lost`, `Damaged`, `Disposed`, `Other Events`, `Ending Warehouse Balance`, `Unknown Events`, `Location`, `Store`

### GET_MERCHANT_LISTINGS_ALL_DATA

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_MERCHANT_LISTINGS_ALL_DATA.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `6` |
| Observed field/path count | `29` |
| Status | `sampled + analyzed` |
| Data domain | Listing snapshot and SKU/ASIN listing metadata |

Observed source fields:

`item-name`, `item-description`, `listing-id`, `seller-sku`, `price`, `quantity`, `open-date`, `image-url`, `item-is-marketplace`, `product-id-type`, `zshop-shipping-fee`, `item-note`, `item-condition`, `zshop-category1`, `zshop-browse-path`, `zshop-storefront-feature`, `asin1`, `asin2`, `asin3`, `will-ship-internationally`, `expedited-shipping`, `zshop-boldface`, `product-id`, `bid-for-featured-placement`, `add-delete`, `pending-quantity`, `fulfillment-channel`, `merchant-shipping-group`, `status`

### GET_PROMOTION_PERFORMANCE_REPORT

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport with promotionStartDateFrom / promotionStartDateTo reportOptions |
| Current sample file | `requirements/data_samples/GET_PROMOTION_PERFORMANCE_REPORT.md` |
| Format | `json` |
| Delimiter | `n/a` |
| Current sample rows | `1` |
| Observed field/path count | `24` |
| Status | `sampled + analyzed` |
| Data domain | Promotion performance |

Observed source fields:

`promotions[].createdDateTime`, `promotions[].endDateTime`, `promotions[].glanceViews`, `promotions[].includedProducts[].asin`, `promotions[].includedProducts[].productGlanceViews`, `promotions[].includedProducts[].productName`, `promotions[].includedProducts[].productRevenue`, `promotions[].includedProducts[].productRevenueCurrencyCode`, `promotions[].includedProducts[].productUnitsSold`, `promotions[].lastUpdatedDateTime`, `promotions[].marketplaceId`, `promotions[].merchantId`, `promotions[].promotionId`, `promotions[].promotionName`, `promotions[].revenue`, `promotions[].revenueCurrencyCode`, `promotions[].startDateTime`, `promotions[].status`, `promotions[].type`, `promotions[].unitsSold`, `reportSpecification.marketplaceIds[]`, `reportSpecification.reportOptions.promotionStartDateFrom`, `reportSpecification.reportOptions.promotionStartDateTo`, `reportSpecification.reportType`

Notes:

- Diagnostic sampling confirmed required date reportOptions; current sample with options is available.

### GET_RESERVED_INVENTORY_DATA

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_RESERVED_INVENTORY_DATA.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `5` |
| Observed field/path count | `9` |
| Status | `sampled + analyzed` |
| Data domain | Reserved FBA inventory |

Observed source fields:

`sku`, `fnsku`, `asin`, `product-name`, `reserved_qty`, `reserved_customerorders`, `reserved_fc-transfers`, `reserved_fc-processing`, `program`

### GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `5` |
| Observed field/path count | `30` |
| Status | `sampled + analyzed` |
| Data domain | Restock recommendations |

Observed source fields:

`Country`, `Product Name`, `FNSKU`, `Merchant SKU`, `ASIN`, `Condition`, `Supplier`, `Supplier part no.`, `Currency code`, `Price`, `Sales last 30 days`, `Units Sold Last 30 Days`, `Total Units`, `Inbound`, `Available`, `FC transfer`, `FC Processing`, `Customer Order`, `Unfulfillable`, `Working`, `Shipped`, `Receiving`, `Fulfilled by`, `Total Days of Supply (including units from open shipments)`, `Days of Supply at Amazon Fulfillment Network`, `Alert`, `Recommended replenishment qty`, `Recommended ship date`, `Recommended action`, `Unit storage size`

### GET_SALES_AND_TRAFFIC_REPORT

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | createReport -> getReport/getReportDocument |
| Current sample file | `requirements/data_samples/GET_SALES_AND_TRAFFIC_REPORT.md` |
| Format | `json` |
| Delimiter | `n/a` |
| Current sample rows | `6` |
| Observed field/path count | `94` |
| Status | `sampled + analyzed` |
| Data domain | Sales and traffic metrics by date and ASIN |

Observed source fields:

`reportSpecification.dataEndTime`, `reportSpecification.dataStartTime`, `reportSpecification.marketplaceIds[]`, `reportSpecification.reportOptions.asinGranularity`, `reportSpecification.reportOptions.dateGranularity`, `reportSpecification.reportType`, `salesAndTrafficByAsin[].parentAsin`, `salesAndTrafficByAsin[].salesByAsin.orderedProductSales.amount`, `salesAndTrafficByAsin[].salesByAsin.orderedProductSales.currencyCode`, `salesAndTrafficByAsin[].salesByAsin.orderedProductSalesB2B.amount`, `salesAndTrafficByAsin[].salesByAsin.orderedProductSalesB2B.currencyCode`, `salesAndTrafficByAsin[].salesByAsin.totalOrderItems`, `salesAndTrafficByAsin[].salesByAsin.totalOrderItemsB2B`, `salesAndTrafficByAsin[].salesByAsin.unitsOrdered`, `salesAndTrafficByAsin[].salesByAsin.unitsOrderedB2B`, `salesAndTrafficByAsin[].trafficByAsin.browserPageViews`, `salesAndTrafficByAsin[].trafficByAsin.browserPageViewsB2B`, `salesAndTrafficByAsin[].trafficByAsin.browserPageViewsPercentage`, `salesAndTrafficByAsin[].trafficByAsin.browserPageViewsPercentageB2B`, `salesAndTrafficByAsin[].trafficByAsin.browserSessionPercentage`, `salesAndTrafficByAsin[].trafficByAsin.browserSessionPercentageB2B`, `salesAndTrafficByAsin[].trafficByAsin.browserSessions`, `salesAndTrafficByAsin[].trafficByAsin.browserSessionsB2B`, `salesAndTrafficByAsin[].trafficByAsin.buyBoxPercentage`, `salesAndTrafficByAsin[].trafficByAsin.buyBoxPercentageB2B`, `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViews`, `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsB2B`, `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsPercentage`, `salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsPercentageB2B`, `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionPercentage`, `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionPercentageB2B`, `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessions`, `salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionsB2B`, `salesAndTrafficByAsin[].trafficByAsin.pageViews`, `salesAndTrafficByAsin[].trafficByAsin.pageViewsB2B`, `salesAndTrafficByAsin[].trafficByAsin.pageViewsPercentage`, `salesAndTrafficByAsin[].trafficByAsin.pageViewsPercentageB2B`, `salesAndTrafficByAsin[].trafficByAsin.sessionPercentage`, `salesAndTrafficByAsin[].trafficByAsin.sessionPercentageB2B`, `salesAndTrafficByAsin[].trafficByAsin.sessions`, `salesAndTrafficByAsin[].trafficByAsin.sessionsB2B`, `salesAndTrafficByAsin[].trafficByAsin.unitSessionPercentage`, `salesAndTrafficByAsin[].trafficByAsin.unitSessionPercentageB2B`, `salesAndTrafficByDate[].date`, `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItem.amount`, `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItem.currencyCode`, `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItemB2B.amount`, `salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItemB2B.currencyCode`, `salesAndTrafficByDate[].salesByDate.averageSellingPrice.amount`, `salesAndTrafficByDate[].salesByDate.averageSellingPrice.currencyCode`, `salesAndTrafficByDate[].salesByDate.averageSellingPriceB2B.amount`, `salesAndTrafficByDate[].salesByDate.averageSellingPriceB2B.currencyCode`, `salesAndTrafficByDate[].salesByDate.averageUnitsPerOrderItem`, `salesAndTrafficByDate[].salesByDate.averageUnitsPerOrderItemB2B`, `salesAndTrafficByDate[].salesByDate.claimsAmount.amount`, `salesAndTrafficByDate[].salesByDate.claimsAmount.currencyCode`, `salesAndTrafficByDate[].salesByDate.claimsGranted`, `salesAndTrafficByDate[].salesByDate.orderedProductSales.amount`, `salesAndTrafficByDate[].salesByDate.orderedProductSales.currencyCode`, `salesAndTrafficByDate[].salesByDate.orderedProductSalesB2B.amount`, `salesAndTrafficByDate[].salesByDate.orderedProductSalesB2B.currencyCode`, `salesAndTrafficByDate[].salesByDate.ordersShipped`, `salesAndTrafficByDate[].salesByDate.refundRate`, `salesAndTrafficByDate[].salesByDate.shippedProductSales.amount`, `salesAndTrafficByDate[].salesByDate.shippedProductSales.currencyCode`, `salesAndTrafficByDate[].salesByDate.totalOrderItems`, `salesAndTrafficByDate[].salesByDate.totalOrderItemsB2B`, `salesAndTrafficByDate[].salesByDate.unitsOrdered`, `salesAndTrafficByDate[].salesByDate.unitsOrderedB2B`, `salesAndTrafficByDate[].salesByDate.unitsRefunded`, `salesAndTrafficByDate[].salesByDate.unitsShipped`, `salesAndTrafficByDate[].trafficByDate.averageOfferCount`, `salesAndTrafficByDate[].trafficByDate.averageParentItems`, `salesAndTrafficByDate[].trafficByDate.browserPageViews`, `salesAndTrafficByDate[].trafficByDate.browserPageViewsB2B`, `salesAndTrafficByDate[].trafficByDate.browserSessions`, `salesAndTrafficByDate[].trafficByDate.browserSessionsB2B`, `salesAndTrafficByDate[].trafficByDate.buyBoxPercentage`, `salesAndTrafficByDate[].trafficByDate.buyBoxPercentageB2B`, `salesAndTrafficByDate[].trafficByDate.feedbackReceived`, `salesAndTrafficByDate[].trafficByDate.mobileAppPageViews`, `salesAndTrafficByDate[].trafficByDate.mobileAppPageViewsB2B`, `salesAndTrafficByDate[].trafficByDate.mobileAppSessions`, `salesAndTrafficByDate[].trafficByDate.mobileAppSessionsB2B`, `salesAndTrafficByDate[].trafficByDate.negativeFeedbackReceived`, `salesAndTrafficByDate[].trafficByDate.orderItemSessionPercentage`, `salesAndTrafficByDate[].trafficByDate.orderItemSessionPercentageB2B`, `salesAndTrafficByDate[].trafficByDate.pageViews`, `salesAndTrafficByDate[].trafficByDate.pageViewsB2B`, `salesAndTrafficByDate[].trafficByDate.receivedNegativeFeedbackRate`, `salesAndTrafficByDate[].trafficByDate.sessions`, `salesAndTrafficByDate[].trafficByDate.sessionsB2B`, `salesAndTrafficByDate[].trafficByDate.unitSessionPercentage`, `salesAndTrafficByDate[].trafficByDate.unitSessionPercentageB2B`

### GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2

| Item | Value |
|---|---|
| Source | SP-API Reports |
| Acquisition | getReports discovery; Amazon-generated settlement report, not createReport |
| Current sample file | `requirements/data_samples/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.md` |
| Format | `delimited` |
| Delimiter | `tab` |
| Current sample rows | `4911` |
| Observed field/path count | `24` |
| Status | `discovered + sampled aggregate` |
| Data domain | Settlement financial ledger and settlement summary |

Observed source fields:

`settlement-id`, `settlement-start-date`, `settlement-end-date`, `deposit-date`, `total-amount`, `currency`, `transaction-type`, `order-id`, `merchant-order-id`, `adjustment-id`, `shipment-id`, `marketplace-name`, `amount-type`, `amount-description`, `amount`, `fulfillment-id`, `posted-date`, `posted-date-time`, `order-item-code`, `merchant-order-item-id`, `merchant-adjustment-item-id`, `sku`, `quantity-purchased`, `promotion-id`

Notes:

- Current aggregate sample covers `8` raw file(s).

## 4. 已列入计划但当前无有效字段样例的报告

| report_type | 获取方式 | 数据域 | 当前状态 / 说明 |
|---|---|---|---|
| `GET_STRANDED_INVENTORY_UI_DATA` | SP-API Reports createReport | FBA stranded inventory | current account returned cancelled/no-data in sampling; no sample document yet |
| `GET_FBA_RECOMMENDED_REMOVAL_DATA` | SP-API Reports createReport | FBA recommended removal | current account returned cancelled/no-data in sampling; no sample document yet |
| `GET_FBA_STORAGE_FEE_CHARGES_DATA` | SP-API Reports createReport | FBA monthly storage fees | current sampling window returned cancelled/no-data |
| `GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA` | SP-API Reports createReport | FBA long-term storage fees | current sampling window returned cancelled/no-data |
| `GET_FBA_OVERAGE_FEE_CHARGES_DATA` | SP-API Reports createReport | FBA overage fees | current sampling window returned cancelled/no-data |
| `GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA` | SP-API Reports createReport | FBA customer returns | excluded from default sampling because it may include customer comments |
| `GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL` | SP-API Reports createReport | FBA fulfilled shipments | excluded from default sampling because it may include buyer/contact/address fields |

## 5. 诊断文档

当前存在以下 diagnostic 取样记录，它们不是业务报表本身，而是用于确认请求参数要求：

| Diagnostic file | 说明 |
|---|---|
| `requirements/data_samples/GET_PROMOTION_PERFORMANCE_REPORT_DIAGNOSTIC.md` | 用于确认 promotion report 需要 `promotionStartDateFrom` / `promotionStartDateTo`。 |
| `requirements/data_samples/GET_COUPON_PERFORMANCE_REPORT_DIAGNOSTIC.md` | 用于确认 coupon report 需要 `couponStartDateFrom` / `couponStartDateTo`。 |

## 6. 与后续功能的关系

SP-API Reports catalog 只记录“可拿到的数据”。如果要开发某个入库或分析功能，需要在 `docs/features/` 建立对应功能文档，并引用本目录中具体 report type。
