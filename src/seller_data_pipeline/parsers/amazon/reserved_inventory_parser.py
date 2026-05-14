from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from seller_data_pipeline.parsers.amazon.flat_file_utils import (
    AmazonFlatFileParser,
    compute_source_row_hash,
    empty_to_none,
    parse_int,
)

RESERVED_INVENTORY_REPORT_TYPE = "GET_RESERVED_INVENTORY_DATA"

RESERVED_INVENTORY_REQUIRED_FIELDS = {
    "sku",
    "fnsku",
    "asin",
    "product-name",
    "reserved_qty",
    "reserved_customerorders",
    "reserved_fc-transfers",
    "reserved_fc-processing",
    "program",
}


@dataclass(frozen=True)
class ReservedInventoryRecord:
    marketplace_id: str
    seller_sku: str | None
    fnsku: str | None
    asin: str | None
    product_name: str | None
    reserved_quantity: int | None
    reserved_customer_orders: int | None
    reserved_fc_transfers: int | None
    reserved_fc_processing: int | None
    program: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReservedInventoryParser(AmazonFlatFileParser):
    """Parser for GET_RESERVED_INVENTORY_DATA reports."""

    report_type = RESERVED_INVENTORY_REPORT_TYPE
    required_fields = RESERVED_INVENTORY_REQUIRED_FIELDS

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> ReservedInventoryRecord:
        return ReservedInventoryRecord(
            marketplace_id=marketplace_id,
            seller_sku=empty_to_none(row.get("sku")),
            fnsku=empty_to_none(row.get("fnsku")),
            asin=empty_to_none(row.get("asin")),
            product_name=empty_to_none(row.get("product-name")),
            reserved_quantity=parse_int(row.get("reserved_qty")),
            reserved_customer_orders=parse_int(row.get("reserved_customerorders")),
            reserved_fc_transfers=parse_int(row.get("reserved_fc-transfers")),
            reserved_fc_processing=parse_int(row.get("reserved_fc-processing")),
            program=empty_to_none(row.get("program")),
            source_system="sp_api_reports",
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )
