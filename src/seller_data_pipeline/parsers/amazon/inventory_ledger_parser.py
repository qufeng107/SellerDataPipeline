from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from seller_data_pipeline.parsers.amazon.flat_file_utils import (
    AmazonFlatFileParser,
    compute_source_row_hash,
    empty_to_none,
    parse_int,
)

LEDGER_SUMMARY_REPORT_TYPE = "GET_LEDGER_SUMMARY_VIEW_DATA"

LEDGER_SUMMARY_REQUIRED_FIELDS = {
    "Date",
    "FNSKU",
    "ASIN",
    "MSKU",
    "Title",
    "Disposition",
    "Starting Warehouse Balance",
    "In Transit Between Warehouses",
    "Receipts",
    "Customer Shipments",
    "Customer Returns",
    "Vendor Returns",
    "Warehouse Transfer In/Out",
    "Found",
    "Lost",
    "Damaged",
    "Disposed",
    "Other Events",
    "Ending Warehouse Balance",
    "Unknown Events",
    "Location",
    "Store",
}


@dataclass(frozen=True)
class InventoryLedgerSummaryRecord:
    marketplace_id: str
    ledger_date_raw: str | None
    fnsku: str | None
    asin: str | None
    seller_sku: str | None
    title: str | None
    disposition: str | None
    starting_warehouse_balance: int | None
    in_transit_between_warehouses: int | None
    receipts: int | None
    customer_shipments: int | None
    customer_returns: int | None
    vendor_returns: int | None
    warehouse_transfer_in_out: int | None
    found: int | None
    lost: int | None
    damaged: int | None
    disposed: int | None
    other_events: int | None
    ending_warehouse_balance: int | None
    unknown_events: int | None
    location: str | None
    store: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InventoryLedgerSummaryParser(AmazonFlatFileParser):
    """Parser for GET_LEDGER_SUMMARY_VIEW_DATA reports."""

    report_type = LEDGER_SUMMARY_REPORT_TYPE
    required_fields = LEDGER_SUMMARY_REQUIRED_FIELDS

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> InventoryLedgerSummaryRecord:
        return InventoryLedgerSummaryRecord(
            marketplace_id=marketplace_id,
            ledger_date_raw=empty_to_none(row.get("Date")),
            fnsku=empty_to_none(row.get("FNSKU")),
            asin=empty_to_none(row.get("ASIN")),
            seller_sku=empty_to_none(row.get("MSKU")),
            title=empty_to_none(row.get("Title")),
            disposition=empty_to_none(row.get("Disposition")),
            starting_warehouse_balance=parse_int(row.get("Starting Warehouse Balance")),
            in_transit_between_warehouses=parse_int(
                row.get("In Transit Between Warehouses")
            ),
            receipts=parse_int(row.get("Receipts")),
            customer_shipments=parse_int(row.get("Customer Shipments")),
            customer_returns=parse_int(row.get("Customer Returns")),
            vendor_returns=parse_int(row.get("Vendor Returns")),
            warehouse_transfer_in_out=parse_int(row.get("Warehouse Transfer In/Out")),
            found=parse_int(row.get("Found")),
            lost=parse_int(row.get("Lost")),
            damaged=parse_int(row.get("Damaged")),
            disposed=parse_int(row.get("Disposed")),
            other_events=parse_int(row.get("Other Events")),
            ending_warehouse_balance=parse_int(row.get("Ending Warehouse Balance")),
            unknown_events=parse_int(row.get("Unknown Events")),
            location=empty_to_none(row.get("Location")),
            store=empty_to_none(row.get("Store")),
            source_system="sp_api_reports",
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )

LEDGER_DETAIL_REPORT_TYPE = "GET_LEDGER_DETAIL_VIEW_DATA"

LEDGER_DETAIL_REQUIRED_FIELDS = {
    "Date",
    "FNSKU",
    "ASIN",
    "MSKU",
    "Title",
    "Event Type",
    "Reference ID",
    "Quantity",
    "Fulfillment Center",
    "Disposition",
    "Reason",
    "Country",
    "Reconciled Quantity",
    "Unreconciled Quantity",
    "Date and Time",
    "Store",
}


@dataclass(frozen=True)
class InventoryLedgerDetailRecord:
    marketplace_id: str
    ledger_date_raw: str | None
    fnsku: str | None
    asin: str | None
    seller_sku: str | None
    title: str | None
    event_type: str | None
    reference_id: str | None
    quantity: int | None
    fulfillment_center: str | None
    disposition: str | None
    reason: str | None
    country: str | None
    reconciled_quantity: int | None
    unreconciled_quantity: int | None
    date_time_raw: str | None
    store: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InventoryLedgerDetailParser(AmazonFlatFileParser):
    """Parser for GET_LEDGER_DETAIL_VIEW_DATA reports."""

    report_type = LEDGER_DETAIL_REPORT_TYPE
    required_fields = LEDGER_DETAIL_REQUIRED_FIELDS

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> InventoryLedgerDetailRecord:
        return InventoryLedgerDetailRecord(
            marketplace_id=marketplace_id,
            ledger_date_raw=empty_to_none(row.get("Date")),
            fnsku=empty_to_none(row.get("FNSKU")),
            asin=empty_to_none(row.get("ASIN")),
            seller_sku=empty_to_none(row.get("MSKU")),
            title=empty_to_none(row.get("Title")),
            event_type=empty_to_none(row.get("Event Type")),
            reference_id=empty_to_none(row.get("Reference ID")),
            quantity=parse_int(row.get("Quantity")),
            fulfillment_center=empty_to_none(row.get("Fulfillment Center")),
            disposition=empty_to_none(row.get("Disposition")),
            reason=empty_to_none(row.get("Reason")),
            country=empty_to_none(row.get("Country")),
            reconciled_quantity=parse_int(row.get("Reconciled Quantity")),
            unreconciled_quantity=parse_int(row.get("Unreconciled Quantity")),
            date_time_raw=empty_to_none(row.get("Date and Time")),
            store=empty_to_none(row.get("Store")),
            source_system="sp_api_reports",
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )
