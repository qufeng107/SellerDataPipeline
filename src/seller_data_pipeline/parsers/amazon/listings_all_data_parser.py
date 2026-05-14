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

LISTINGS_ALL_DATA_REQUIRED_FIELDS = {
    "listing-id",
    "seller-sku",
    "asin1",
    "product-id",
    "product-id-type",
    "item-name",
    "price",
    "open-date",
    "item-condition",
    "fulfillment-channel",
    "status",
}


@dataclass(frozen=True)
class ListingSnapshotRecord:
    marketplace_id: str
    snapshot_date: str
    listing_id: str
    seller_sku: str
    asin: str | None
    product_id: str | None
    product_id_type: str | None
    item_name: str | None
    item_description: str | None
    price: Decimal | None
    currency: str | None
    quantity: int | None
    pending_quantity: int | None
    open_date_raw: str | None
    item_is_marketplace: bool | None
    item_condition: str | None
    fulfillment_channel: str | None
    merchant_shipping_group: str | None
    status: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.price is not None:
            payload["price"] = str(self.price)
        return payload


class ListingsAllDataParser:
    """Parser for SP-API GET_MERCHANT_LISTINGS_ALL_DATA flat files."""

    def parse_file(
        self,
        *,
        raw_file_path: str | Path,
        marketplace_id: str,
        snapshot_date: date | None = None,
        currency: str | None = "USD",
        source_report_id: str | None = None,
    ) -> list[ListingSnapshotRecord]:
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
    ) -> list[ListingSnapshotRecord]:
        text, _encoding = decode_report_content(content)
        delimiter = detect_report_delimiter(text)
        if delimiter is None:
            raise ValueError("Listing report must be a delimited flat file")
        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        fieldnames = set(reader.fieldnames or [])
        missing_fields = sorted(LISTINGS_ALL_DATA_REQUIRED_FIELDS - fieldnames)
        if missing_fields:
            raise ValueError(f"Missing required listing report fields: {missing_fields}")

        effective_snapshot_date = snapshot_date or datetime.now(UTC).date()
        records: list[ListingSnapshotRecord] = []
        for raw_row in reader:
            row = {str(key): (value or "").strip() for key, value in raw_row.items() if key}
            records.append(
                ListingSnapshotRecord(
                    marketplace_id=marketplace_id,
                    snapshot_date=effective_snapshot_date.isoformat(),
                    listing_id=row["listing-id"],
                    seller_sku=row["seller-sku"],
                    asin=_empty_to_none(row.get("asin1")),
                    product_id=_empty_to_none(row.get("product-id")),
                    product_id_type=_empty_to_none(row.get("product-id-type")),
                    item_name=_empty_to_none(row.get("item-name")),
                    item_description=_empty_to_none(row.get("item-description")),
                    price=_parse_decimal(row.get("price")),
                    currency=currency,
                    quantity=_parse_int(row.get("quantity")),
                    pending_quantity=_parse_int(row.get("pending-quantity")),
                    open_date_raw=_empty_to_none(row.get("open-date")),
                    item_is_marketplace=_parse_yes_no(row.get("item-is-marketplace")),
                    item_condition=_empty_to_none(row.get("item-condition")),
                    fulfillment_channel=_empty_to_none(row.get("fulfillment-channel")),
                    merchant_shipping_group=_empty_to_none(row.get("merchant-shipping-group")),
                    status=_empty_to_none(row.get("status")),
                    source_system="sp_api_reports",
                    source_report_type="GET_MERCHANT_LISTINGS_ALL_DATA",
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
