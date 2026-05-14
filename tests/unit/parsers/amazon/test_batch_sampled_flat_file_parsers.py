from __future__ import annotations

from seller_data_pipeline.parsers.amazon.fba_estimated_fees_parser import FbaEstimatedFeesParser
from seller_data_pipeline.parsers.amazon.fba_reimbursements_parser import FbaReimbursementsParser
from seller_data_pipeline.parsers.amazon.inventory_ledger_parser import InventoryLedgerSummaryParser
from seller_data_pipeline.parsers.amazon.inventory_planning_parser import FbaInventoryPlanningParser
from seller_data_pipeline.parsers.amazon.orders_report_parser import AllOrdersReportParser
from seller_data_pipeline.parsers.amazon.returns_report_parser import ReturnsByReturnDateParser


def test_all_orders_parser_parses_money_and_flags() -> None:
    content = (
        "amazon-order-id\tmerchant-order-id\tpurchase-date\tlast-updated-date\t"
        "order-status\tfulfillment-channel\tsales-channel\torder-channel\t"
        "ship-service-level\tproduct-name\tsku\tasin\titem-status\tquantity\t"
        "currency\titem-price\titem-tax\tshipping-price\tshipping-tax\t"
        "gift-wrap-price\tgift-wrap-tax\titem-promotion-discount\t"
        "ship-promotion-discount\tship-city\tship-state\tship-postal-code\t"
        "ship-country\tpromotion-ids\tcpf\tis-business-order\t"
        "purchase-order-number\tprice-designation\tsignature-confirmation-recommended\n"
        "111-1\tM1\t2026-05-01T00:00:00+00:00\t2026-05-01T01:00:00+00:00\t"
        "Shipped\tAmazon\tAmazon.com\t\tStandard\tProduct\tSKU1\tASIN1\tShipped\t2\t"
        "USD\t25.00\t1.50\t0\t0\t0\t0\t2.00\t0\tSeattle\tWA\t98101\tUS\tPROMO\t\tfalse\t\t\ttrue\n"
    )

    records = AllOrdersReportParser().parse_text(text=content, marketplace_id="ATVPDKIKX0DER")

    assert len(records) == 1
    assert records[0].amazon_order_id == "111-1"
    assert records[0].quantity == 2
    assert records[0].to_dict()["item_price"] == "25.00"
    assert records[0].is_business_order is False
    assert records[0].signature_confirmation_recommended is True


def test_returns_parser_accepts_header_only_report() -> None:
    content = (
        "Order ID\tOrder date\tReturn request date\tReturn request status\tAmazon RMA ID\t"
        "Merchant RMA ID\tLabel type\tLabel cost\tCurrency code\tReturn carrier\tTracking ID\t"
        "Label to be paid by\tA-to-Z Claim\tIs prime\tASIN\tMerchant SKU\tItem Name\t"
        "Return quantity\tReturn Reason\tIn policy\tReturn type\tResolution\tInvoice number\t"
        "Return delivery date\tOrder Amount\tOrder quantity\tSafeT Action reason\tSafeT claim id\t"
        "SafeT claim state\tSafeT claim creation time\tSafeT claim reimbursement amount\t"
        "Refunded Amount\tOrder Item ID\n"
    )

    records = ReturnsByReturnDateParser().parse_text(text=content, marketplace_id="ATVPDKIKX0DER")

    assert records == []


def test_fba_reimbursements_parser_parses_amounts_and_quantities() -> None:
    content = (
        "approval-date\treimbursement-id\tcase-id\tamazon-order-id\treason\tsku\tfnsku\t"
        "asin\tproduct-name\tcondition\tcurrency-unit\tamount-per-unit\tamount-total\t"
        "quantity-reimbursed-cash\tquantity-reimbursed-inventory\tquantity-reimbursed-total\t"
        "original-reimbursement-id\toriginal-reimbursement-type\n"
        "2026-05-12T09:59:13+00:00\tR1\tC1\t111-1\tCustomerReturn\tSKU1\tFNSKU1\t"
        "ASIN1\tProduct\tNewItem\tUSD\t12.34\t24.68\t2\t0\t2\t\t\n"
    )

    records = FbaReimbursementsParser().parse_text(text=content, marketplace_id="ATVPDKIKX0DER")

    assert len(records) == 1
    assert records[0].reason == "CustomerReturn"
    assert records[0].quantity_reimbursed_total == 2
    assert records[0].to_dict()["amount_total"] == "24.68"


def test_fba_estimated_fees_parser_parses_fee_columns() -> None:
    content = (
        "sku\tfnsku\tasin\tamazon-store\tproduct-name\tproduct-group\tbrand\tfulfilled-by\t"
        "your-price\tsales-price\tlongest-side\tmedian-side\tshortest-side\tlength-and-girth\t"
        "unit-of-dimension\titem-package-weight\tunit-of-weight\tproduct-size-tier\tcurrency\t"
        "estimated-fee-total\testimated-referral-fee-per-unit\testimated-variable-closing-fee\t"
        "estimated-order-handling-fee-per-order\testimated-pick-pack-fee-per-unit\t"
        "estimated-weight-handling-fee-per-unit\texpected-fulfillment-fee-per-unit\t"
        "estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)\t"
        "estimated-future-order-handling-fee-per-order\testimated-future-pick-pack-fee-per-unit\t"
        "estimated-future-weight-handling-fee-per-unit\texpected-future-fulfillment-fee-per-unit\n"
        "SKU1\tFNSKU1\tASIN1\tUS\tProduct\tLuggage\tBrand\tAmazon\t25.00\t25.00\t"
        "6\t4\t1\t10\tinches\t0.5\tpounds\tSmall standard\tUSD\t8.01\t3.75\t0\t0\t"
        "4.26\t0\t4.26\t8.50\t0\t4.50\t0\t4.50\n"
    )

    records = FbaEstimatedFeesParser().parse_text(text=content, marketplace_id="ATVPDKIKX0DER")

    assert len(records) == 1
    assert records[0].amazon_store == "US"
    assert records[0].to_dict()["estimated_fee_total"] == "8.01"
    assert records[0].to_dict()["expected_fulfillment_fee_per_unit"] == "4.26"


def test_inventory_planning_parser_parses_core_health_fields() -> None:
    content = (
        "snapshot-date\tsku\tfnsku\tasin\tproduct-name\tcondition\tavailable\t"
        "pending-removal-quantity\tinv-age-0-to-90-days\tinv-age-91-to-180-days\t"
        "inv-age-181-to-270-days\tinv-age-271-to-365-days\tinv-age-366-to-455-days\t"
        "inv-age-456-plus-days\tcurrency\tunits-shipped-t7\tunits-shipped-t30\t"
        "units-shipped-t60\tunits-shipped-t90\talert\tyour-price\tsales-price\t"
        "lowest-price-new-plus-shipping\tlowest-price-used\trecommended-action\t"
        "DEPRECATED healthy-inventory-level\trecommended-sales-price\t"
        "recommended-sale-duration-days\trecommended-removal-quantity\t"
        "estimated-cost-savings-of-recommended-actions\tsell-through\titem-volume\t"
        "volume-unit-measurement\tstorage-type\tstorage-volume\tmarketplace\tproduct-group\t"
        "sales-rank\tdays-of-supply\testimated-excess-quantity\n"
        "2026-05-14\tSKU1\tFNSKU1\tASIN1\tProduct\tNew\t10\t0\t8\t2\t0\t0\t0\t0\t"
        "USD\t1\t5\t6\t7\t\t25.00\t\t\t\t\t\t\t\t0\t0\t1.25\t10\tcubic feet\t"
        "standard\t12\tUS\tLuggage\t100\t20\t0\n"
    )

    records = FbaInventoryPlanningParser().parse_text(text=content, marketplace_id="ATVPDKIKX0DER")

    assert len(records) == 1
    assert records[0].available_quantity == 10
    assert records[0].units_shipped_t30 == 5
    assert records[0].to_dict()["days_of_supply"] == "20"


def test_inventory_ledger_summary_parser_parses_movement_columns() -> None:
    content = (
        "Date\tFNSKU\tASIN\tMSKU\tTitle\tDisposition\tStarting Warehouse Balance\t"
        "In Transit Between Warehouses\tReceipts\tCustomer Shipments\tCustomer Returns\t"
        "Vendor Returns\tWarehouse Transfer In/Out\tFound\tLost\tDamaged\tDisposed\t"
        "Other Events\tEnding Warehouse Balance\tUnknown Events\tLocation\tStore\n"
        "05/13/2026\tFNSKU1\tASIN1\tSKU1\tProduct\tSELLABLE\t10\t0\t2\t-1\t1\t"
        "0\t0\t0\t-1\t0\t0\t0\t11\t0\tUS\t\n"
    )

    records = InventoryLedgerSummaryParser().parse_text(
        text=content,
        marketplace_id="ATVPDKIKX0DER",
    )

    assert len(records) == 1
    assert records[0].seller_sku == "SKU1"
    assert records[0].receipts == 2
    assert records[0].customer_shipments == -1
    assert records[0].ending_warehouse_balance == 11


def test_inventory_ledger_detail_parser_parses_event_rows() -> None:
    from seller_data_pipeline.parsers.amazon.inventory_ledger_parser import (
        InventoryLedgerDetailParser,
    )

    content = (
        "Date\tFNSKU\tASIN\tMSKU\tTitle\tEvent Type\tReference ID\tQuantity\t"
        "Fulfillment Center\tDisposition\tReason\tCountry\tReconciled Quantity\t"
        "Unreconciled Quantity\tDate and Time\tStore\n"
        "05/13/2026\tFNSKU1\tASIN1\tSKU1\tProduct\tShipments\tREF1\t-1\t"
        "PHL7\tSELLABLE\t\tUS\t0\t-1\t05/13/2026 09:00:00\tUS\n"
    )

    records = InventoryLedgerDetailParser().parse_text(
        text=content,
        marketplace_id="ATVPDKIKX0DER",
    )

    assert len(records) == 1
    assert records[0].event_type == "Shipments"
    assert records[0].quantity == -1
    assert records[0].fulfillment_center == "PHL7"


def test_reserved_inventory_parser_parses_reserved_buckets() -> None:
    from seller_data_pipeline.parsers.amazon.reserved_inventory_parser import (
        ReservedInventoryParser,
    )

    content = (
        "sku\tfnsku\tasin\tproduct-name\treserved_qty\treserved_customerorders\t"
        "reserved_fc-transfers\treserved_fc-processing\tprogram\n"
        "SKU1\tFNSKU1\tASIN1\tProduct\t7\t1\t2\t4\t\n"
    )

    records = ReservedInventoryParser().parse_text(
        text=content,
        marketplace_id="ATVPDKIKX0DER",
    )

    assert len(records) == 1
    assert records[0].reserved_quantity == 7
    assert records[0].reserved_fc_processing == 4


def test_restock_inventory_parser_parses_recommendations() -> None:
    from seller_data_pipeline.parsers.amazon.restock_inventory_parser import (
        RestockInventoryRecommendationsParser,
    )

    content = (
        "Country\tProduct Name\tFNSKU\tMerchant SKU\tASIN\tCondition\tSupplier\t"
        "Supplier part no.\tCurrency code\tPrice\tSales last 30 days\t"
        "Units Sold Last 30 Days\tTotal Units\tInbound\tAvailable\tFC transfer\t"
        "FC Processing\tCustomer Order\tUnfulfillable\tWorking\tShipped\tReceiving\t"
        "Fulfilled by\tTotal Days of Supply (including units from open shipments)\t"
        "Days of Supply at Amazon Fulfillment Network\tAlert\t"
        "Recommended replenishment qty\tRecommended ship date\tRecommended action\t"
        "Unit storage size\n"
        "US\tProduct\tFNSKU1\tSKU1\tASIN1\tNew\tunassigned\t\tUSD\t25.00\t"
        "100.50\t4\t10\t2\t8\t1\t3\t0\t0\t0\t1\t1\tAmazon\t"
        "30\t25\tLow stock\t6\t2026-05-20\tCreate shipment\t1.23\n"
    )

    records = RestockInventoryRecommendationsParser().parse_text(
        text=content,
        marketplace_id="ATVPDKIKX0DER",
    )

    assert len(records) == 1
    assert records[0].recommended_replenishment_quantity == 6
    assert records[0].to_dict()["price"] == "25.00"
    assert records[0].to_dict()["unit_storage_size"] == "1.23"
