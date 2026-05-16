# GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2 聚合取样记录

> 本文件基于已下载的多份 Amazon settlement raw report 生成。
> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段结构、计数和分类建议。

## 1. 样例元数据

| 项目 | 值 |
|---|---|
| source_system | `sp_api_reports` |
| report_type | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` |
| marketplace_id | `ATVPDKIKX0DER` |
| raw_file_count | `8` |
| row_count | `4911` |
| transaction_row_count | `4903` |
| settlement_summary_row_count | `8` |

## 2. 文件级统计

| raw_file_path | rows | transaction_rows | summary_rows |
|---|---:|---:|---:|
| `reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/2026-05-14/100988020532.txt` | 859 | 858 | 1 |
| `reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/2026-05-14/104011020546.txt` | 830 | 829 | 1 |
| `reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/2026-05-14/105008020551.txt` | 4 | 3 | 1 |
| `reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/2026-05-14/106841020560.txt` | 797 | 796 | 1 |
| `reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/2026-05-14/109708020574.txt` | 435 | 434 | 1 |
| `reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/2026-05-14/94996020504.txt` | 1035 | 1034 | 1 |
| `reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/2026-05-14/97988020518.txt` | 949 | 948 | 1 |
| `reports/raw/amazon/ATVPDKIKX0DER/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2/2026-05-14/99030020523.txt` | 2 | 1 | 1 |

## 3. transaction-type 分布

| transaction_type | rows |
|---|---:|
| `Order` | 4385 |
| `Refund` | 442 |
| `other-transaction` | 36 |
| `ServiceFee` | 15 |
| `AmazonFees` | 12 |
| `<blank>` | 8 |
| `Order_Retrocharge` | 6 |
| `Liquidations` | 4 |
| `Refund_Retrocharge` | 3 |

## 4. amount-type 分布

| amount_type | rows |
|---|---:|
| `ItemPrice` | 2238 |
| `ItemFees` | 1160 |
| `ItemWithheldTax` | 957 |
| `Promotion` | 485 |
| `other-transaction` | 20 |
| `FBA Inventory Reimbursement` | 16 |
| `Cost of Advertising` | 15 |
| `<blank>` | 8 |
| `Coupon Performance Based Fee` | 5 |
| `Coupon Participation Fee` | 5 |
| `Deal Performance Based Fee` | 1 |
| `Deal Participation Fee` | 1 |

## 5. amount-description 分布

| amount_description | rows |
|---|---:|
| `Principal` | 1289 |
| `Tax` | 975 |
| `MarketplaceFacilitatorTax-Principal` | 943 |
| `FBAPerUnitFulfillmentFee` | 904 |
| `Shipping` | 440 |
| `Commission` | 217 |
| `RefundCommission` | 20 |
| `ShippingTax` | 18 |
| `ShippingChargeback` | 17 |
| `TransactionTotalAmount` | 15 |
| `MarketplaceFacilitatorTax-Shipping` | 14 |
| `Base fee` | 12 |
| `REVERSAL_REIMBURSEMENT` | 9 |
| `<blank>` | 8 |
| `FBA Inbound Placement Service Fee` | 7 |
| `Subscription Fee` | 5 |
| `COMPENSATED_CLAWBACK` | 4 |
| `Storage Fee` | 3 |
| `Successful charge` | 3 |
| `FREE_REPLACEMENT_REFUND_ITEMS` | 2 |
| `Payable to Amazon` | 2 |
| `LiquidationsBrokerageFee` | 2 |
| `RestockingFee` | 1 |
| `WAREHOUSE_DAMAGE` | 1 |

## 6. 第一版分类分布

### 6.1 profit_bucket

| profit_bucket | rows |
|---|---:|
| `tax_passthrough` | 1950 |
| `revenue` | 1113 |
| `fba_fee` | 911 |
| `promotion_cost` | 485 |
| `amazon_fee` | 219 |
| `refund` | 130 |
| `amazon_fee_refund` | 40 |
| `reimbursement` | 16 |
| `advertising_cost` | 15 |
| `reconciliation` | 13 |
| `promotion_fee` | 12 |
| `fba_storage_fee` | 3 |
| `liquidation` | 2 |
| `liquidation_fee` | 2 |

### 6.2 amount_category

| amount_category | rows |
|---|---:|
| `sales_tax` | 993 |
| `marketplace_facilitator_tax` | 957 |
| `product_sales` | 904 |
| `fba_fulfillment_fee` | 904 |
| `promotion_discount` | 430 |
| `shipping_revenue` | 209 |
| `referral_fee` | 197 |
| `refund_revenue` | 130 |
| `promotion_refund_adjustment` | 55 |
| `commission_refund` | 20 |
| `refund_commission` | 20 |
| `shipping_chargeback` | 17 |
| `inventory_reimbursement` | 16 |
| `advertising_fee` | 15 |
| `coupon_fee` | 10 |
| `settlement_summary` | 8 |
| `fba_inbound_placement_fee` | 7 |
| `subscription_fee` | 5 |
| `settlement_transfer` | 5 |
| `storage_fee` | 3 |
| `deal_fee` | 2 |
| `liquidation_revenue` | 2 |
| `liquidation_fee` | 2 |

## 7. 组合映射样例

| transaction_type | amount_type | amount_description | amount_category | profit_bucket | rows |
|---|---|---|---|---|---:|
| `Order` | `ItemPrice` | `Principal` | `product_sales` | `revenue` | 904 |
| `Order` | `ItemFees` | `FBAPerUnitFulfillmentFee` | `fba_fulfillment_fee` | `fba_fee` | 904 |
| `Order` | `ItemPrice` | `Tax` | `sales_tax` | `tax_passthrough` | 864 |
| `Order` | `ItemWithheldTax` | `MarketplaceFacilitatorTax-Principal` | `marketplace_facilitator_tax` | `tax_passthrough` | 834 |
| `Order` | `Promotion` | `Principal` | `promotion_discount` | `promotion_cost` | 238 |
| `Order` | `ItemPrice` | `Shipping` | `shipping_revenue` | `revenue` | 209 |
| `Order` | `ItemFees` | `Commission` | `referral_fee` | `amazon_fee` | 197 |
| `Order` | `Promotion` | `Shipping` | `promotion_discount` | `promotion_cost` | 192 |
| `Refund` | `ItemPrice` | `Principal` | `refund_revenue` | `refund` | 109 |
| `Refund` | `ItemPrice` | `Tax` | `sales_tax` | `tax_passthrough` | 108 |
| `Refund` | `ItemWithheldTax` | `MarketplaceFacilitatorTax-Principal` | `marketplace_facilitator_tax` | `tax_passthrough` | 106 |
| `Refund` | `Promotion` | `Principal` | `promotion_refund_adjustment` | `promotion_cost` | 36 |
| `Refund` | `ItemPrice` | `Shipping` | `refund_revenue` | `refund` | 20 |
| `Refund` | `ItemFees` | `Commission` | `commission_refund` | `amazon_fee_refund` | 20 |
| `Refund` | `ItemFees` | `RefundCommission` | `refund_commission` | `amazon_fee_refund` | 20 |
| `Refund` | `Promotion` | `Shipping` | `promotion_refund_adjustment` | `promotion_cost` | 19 |
| `Order` | `ItemFees` | `ShippingChargeback` | `shipping_chargeback` | `amazon_fee` | 16 |
| `ServiceFee` | `Cost of Advertising` | `TransactionTotalAmount` | `advertising_fee` | `advertising_cost` | 15 |
| `Order` | `ItemPrice` | `ShippingTax` | `sales_tax` | `tax_passthrough` | 14 |
| `Order` | `ItemWithheldTax` | `MarketplaceFacilitatorTax-Shipping` | `marketplace_facilitator_tax` | `tax_passthrough` | 13 |
| `other-transaction` | `FBA Inventory Reimbursement` | `REVERSAL_REIMBURSEMENT` | `inventory_reimbursement` | `reimbursement` | 9 |
| `<blank>` | `<blank>` | `<blank>` | `settlement_summary` | `reconciliation` | 8 |
| `other-transaction` | `other-transaction` | `FBA Inbound Placement Service Fee` | `fba_inbound_placement_fee` | `fba_fee` | 7 |
| `other-transaction` | `other-transaction` | `Subscription Fee` | `subscription_fee` | `amazon_fee` | 5 |
| `AmazonFees` | `Coupon Performance Based Fee` | `Base fee` | `coupon_fee` | `promotion_fee` | 5 |
| `AmazonFees` | `Coupon Participation Fee` | `Base fee` | `coupon_fee` | `promotion_fee` | 5 |
| `other-transaction` | `FBA Inventory Reimbursement` | `COMPENSATED_CLAWBACK` | `inventory_reimbursement` | `reimbursement` | 4 |
| `other-transaction` | `other-transaction` | `Storage Fee` | `storage_fee` | `fba_storage_fee` | 3 |
| `other-transaction` | `other-transaction` | `Successful charge` | `settlement_transfer` | `reconciliation` | 3 |
| `other-transaction` | `FBA Inventory Reimbursement` | `FREE_REPLACEMENT_REFUND_ITEMS` | `inventory_reimbursement` | `reimbursement` | 2 |
| `Order_Retrocharge` | `ItemPrice` | `Tax` | `sales_tax` | `tax_passthrough` | 2 |
| `Order_Retrocharge` | `ItemPrice` | `ShippingTax` | `sales_tax` | `tax_passthrough` | 2 |
| `Order_Retrocharge` | `ItemWithheldTax` | `MarketplaceFacilitatorTax-Principal` | `marketplace_facilitator_tax` | `tax_passthrough` | 2 |
| `other-transaction` | `other-transaction` | `Payable to Amazon` | `settlement_transfer` | `reconciliation` | 2 |
| `Liquidations` | `ItemPrice` | `Principal` | `liquidation_revenue` | `liquidation` | 2 |
| `Liquidations` | `ItemFees` | `LiquidationsBrokerageFee` | `liquidation_fee` | `liquidation_fee` | 2 |
| `Refund` | `ItemPrice` | `RestockingFee` | `refund_revenue` | `refund` | 1 |
| `Refund` | `ItemPrice` | `ShippingTax` | `sales_tax` | `tax_passthrough` | 1 |
| `Refund` | `ItemWithheldTax` | `MarketplaceFacilitatorTax-Shipping` | `marketplace_facilitator_tax` | `tax_passthrough` | 1 |
| `Refund` | `ItemFees` | `ShippingChargeback` | `shipping_chargeback` | `amazon_fee` | 1 |
| `Refund_Retrocharge` | `ItemPrice` | `Tax` | `sales_tax` | `tax_passthrough` | 1 |
| `Refund_Retrocharge` | `ItemPrice` | `ShippingTax` | `sales_tax` | `tax_passthrough` | 1 |
| `Refund_Retrocharge` | `ItemWithheldTax` | `MarketplaceFacilitatorTax-Principal` | `marketplace_facilitator_tax` | `tax_passthrough` | 1 |
| `AmazonFees` | `Deal Performance Based Fee` | `Base fee` | `deal_fee` | `promotion_fee` | 1 |
| `AmazonFees` | `Deal Participation Fee` | `Base fee` | `deal_fee` | `promotion_fee` | 1 |
| `other-transaction` | `FBA Inventory Reimbursement` | `WAREHOUSE_DAMAGE` | `inventory_reimbursement` | `reimbursement` | 1 |

## 8. 初步结论

1. 结算报告第一行通常是 settlement summary 行，带结算周期、币种和 total amount；后续明细行这些列可能为空。Parser 需要把 summary 元数据向下继承到交易明细。
2. `amount-type` + `amount-description` + `transaction-type` 足以建立第一版费用分类字典，但这只是运营分析分类，不应直接等同会计最终科目。
3. `Cost of Advertising` 已经出现在 settlement 中，后续仍建议再接 Ads API 获取 campaign / keyword 维度表现；settlement 主要用于财务入账口径。
4. Coupon、Deal、Storage Fee、Subscription Fee、FBA Inbound Placement Service Fee、Inventory Reimbursement、Liquidations 都已在样例中出现，应在数据库 spec 中保留分类字段。

## 9. 建议目标表

| 目标表 | 设计状态 | 说明 |
|---|---|---|
| `amazon_settlement_transaction` | `sampling` | 已有多份真实样例，可保存逐行 settlement 明细和第一版分类字段 |
| `amazon_finance_event` | `draft` | 后续从 settlement 明细聚合/归类而来，需等分类规则稳定后确认 |
