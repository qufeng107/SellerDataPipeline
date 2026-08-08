from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.raw_report_files import (
    decode_report_content,
    detect_report_delimiter,
)

FBA_INVENTORY_REQUIRED_FIELDS = {
    "sku",
    "afn-fulfillable-quantity",
}



@dataclass(frozen=True)
class FbaInventorySnapshotRecord:
    marketplace_id: str
    snapshot_date: str
    seller_sku: str
    fnsku: str | None
    asin: str | None
    product_name: str | None
    condition: str | None
    your_price: Decimal | None
    currency: str | None
    mfn_listing_exists: bool | None
    mfn_fulfillable_quantity: int | None
    afn_listing_exists: bool | None
    afn_warehouse_quantity: int | None
    afn_fulfillable_quantity: int | None
    afn_unsellable_quantity: int | None
    afn_reserved_quantity: int | None
    afn_total_quantity: int | None
    per_unit_volume: Decimal | None
    afn_inbound_working_quantity: int | None
    afn_inbound_shipped_quantity: int | None
    afn_inbound_receiving_quantity: int | None
    afn_researching_quantity: int | None
    afn_reserved_future_supply: int | None
    afn_future_supply_buyable: int | None
    store: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.your_price is not None:
            payload["your_price"] = str(self.your_price)
        if self.per_unit_volume is not None:
            payload["per_unit_volume"] = str(self.per_unit_volume)
        return payload


class FbaInventoryParser:
    """Parser for SP-API GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA flat files."""

    def parse_file(
        self,
        *,
        raw_file_path: str | Path,
        marketplace_id: str,
        snapshot_date: date | None = None,
        currency: str | None = "USD",
        source_report_id: str | None = None,
    ) -> list[FbaInventorySnapshotRecord]:
        path = Path(raw_file_path)
        return self.parse_bytes(
            content=path.read_bytes(),
            marketplace_id=marketplace_id,
            snapshot_date=snapshot_date,
            currency=currency,
            source_report_id=source_report_id,
            source_raw_file_path=str(path),
        )

    def parse_bytes(
        self,
        *,
        content: bytes,
        marketplace_id: str,
        snapshot_date: date | None = None,
        currency: str | None = "USD",
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> list[FbaInventorySnapshotRecord]:
        text, _encoding = decode_report_content(content)
        delimiter = detect_report_delimiter(text)
        if delimiter is None:
            raise ValueError("FBA inventory report must be a delimited flat file")

        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        fieldnames = set(reader.fieldnames or [])
        missing_fields = sorted(FBA_INVENTORY_REQUIRED_FIELDS - fieldnames)
        if missing_fields:
            raise ValueError(f"Missing required FBA inventory report fields: {missing_fields}")

        effective_snapshot_date = snapshot_date or datetime.now(UTC).date()
        records: list[FbaInventorySnapshotRecord] = []
        for row_number, raw_row in enumerate(reader, start=2):
            row = {str(key): (value or "").strip() for key, value in raw_row.items() if key}
            seller_sku = _empty_to_none(row.get("sku"))
            if seller_sku is None:
                raise ValueError(f"Missing required FBA inventory sku at row {row_number}")
            records.append(
                FbaInventorySnapshotRecord(
                    marketplace_id=marketplace_id,
                    snapshot_date=effective_snapshot_date.isoformat(),
                    seller_sku=seller_sku,
                    fnsku=_empty_to_none(row.get("fnsku")),
                    asin=_empty_to_none(row.get("asin")),
                    product_name=_empty_to_none(row.get("product-name")),
                    condition=_empty_to_none(row.get("condition")),
                    your_price=_parse_decimal(row.get("your-price")),
                    currency=currency,
                    mfn_listing_exists=_parse_yes_no(row.get("mfn-listing-exists")),
                    mfn_fulfillable_quantity=_parse_int(row.get("mfn-fulfillable-quantity")),
                    afn_listing_exists=_parse_yes_no(row.get("afn-listing-exists")),
                    afn_warehouse_quantity=_parse_int(row.get("afn-warehouse-quantity")),
                    afn_fulfillable_quantity=_parse_int(row.get("afn-fulfillable-quantity")),
                    afn_unsellable_quantity=_parse_int(row.get("afn-unsellable-quantity")),
                    afn_reserved_quantity=_parse_int(row.get("afn-reserved-quantity")),
                    afn_total_quantity=_parse_int(row.get("afn-total-quantity")),
                    per_unit_volume=_parse_decimal(row.get("per-unit-volume")),
                    afn_inbound_working_quantity=_parse_int(
                        row.get("afn-inbound-working-quantity")
                    ),
                    afn_inbound_shipped_quantity=_parse_int(
                        row.get("afn-inbound-shipped-quantity")
                    ),
                    afn_inbound_receiving_quantity=_parse_int(
                        row.get("afn-inbound-receiving-quantity")
                    ),
                    afn_researching_quantity=_parse_int(row.get("afn-researching-quantity")),
                    afn_reserved_future_supply=_parse_int(row.get("afn-reserved-future-supply")),
                    afn_future_supply_buyable=_parse_int(row.get("afn-future-supply-buyable")),
                    store=_empty_to_none(row.get("store")),
                    source_system="sp_api_reports",
                    source_report_type="GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA",
                    source_report_id=source_report_id,
                    source_raw_file_path=source_raw_file_path,
                    source_row_hash=compute_source_row_hash(row),
                    raw_data=row,
                )
            )
        return records


def compute_source_row_hash(row: dict[str, str]) -> str:
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _empty_to_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _parse_int(value: str | None) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    return int(value)


def _parse_decimal(value: str | None) -> Decimal | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def _parse_yes_no(value: str | None) -> bool | None:
    value = (value or "").strip().lower()
    if not value:
        return None
    if value in {"y", "yes", "true", "1"}:
        return True
    if value in {"n", "no", "false", "0"}:
        return False
    raise ValueError(f"Invalid yes/no value: {value!r}")
