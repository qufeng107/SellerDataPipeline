from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.raw_report_files import (
    decode_report_content,
    detect_report_delimiter,
)

SETTLEMENT_V2_REPORT_TYPE = "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2"

SETTLEMENT_V2_REQUIRED_FIELDS = {
    "settlement-id",
    "settlement-start-date",
    "settlement-end-date",
    "deposit-date",
    "total-amount",
    "currency",
    "transaction-type",
    "order-id",
    "merchant-order-id",
    "adjustment-id",
    "shipment-id",
    "marketplace-name",
    "amount-type",
    "amount-description",
    "amount",
    "fulfillment-id",
    "posted-date",
    "posted-date-time",
    "order-item-code",
    "merchant-order-item-id",
    "merchant-adjustment-item-id",
    "sku",
    "quantity-purchased",
    "promotion-id",
}


@dataclass(frozen=True)
class SettlementAmountClassification:
    """First-pass finance classification for a settlement report row."""

    amount_category: str
    profit_bucket: str


@dataclass(frozen=True)
class SettlementV2TransactionRecord:
    marketplace_id: str
    settlement_id: str | None
    settlement_start_date_raw: str | None
    settlement_end_date_raw: str | None
    deposit_date_raw: str | None
    total_amount: Decimal | None
    currency: str | None
    is_settlement_summary: bool
    transaction_type: str | None
    order_id: str | None
    merchant_order_id: str | None
    adjustment_id: str | None
    shipment_id: str | None
    marketplace_name: str | None
    amount_type: str | None
    amount_description: str | None
    amount: Decimal | None
    amount_category: str
    profit_bucket: str
    fulfillment_id: str | None
    posted_date_raw: str | None
    posted_date_time_raw: str | None
    order_item_code: str | None
    merchant_order_item_id: str | None
    merchant_adjustment_item_id: str | None
    seller_sku: str | None
    quantity_purchased: int | None
    promotion_id: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = str(value)
        return payload


class SettlementReportParser:
    """Parser for SP-API GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2 reports."""

    def parse_file(
        self,
        *,
        raw_file_path: str | Path,
        marketplace_id: str,
        source_report_id: str | None = None,
    ) -> list[SettlementV2TransactionRecord]:
        path = Path(raw_file_path)
        return self.parse_bytes(
            content=path.read_bytes(),
            marketplace_id=marketplace_id,
            source_report_id=source_report_id,
            source_raw_file_path=str(path),
        )

    def parse(self, content: str) -> list[dict[str, Any]]:
        """Backward-compatible parser entrypoint returning dictionaries."""

        records = self.parse_text(text=content, marketplace_id="UNKNOWN")
        return [record.to_dict() for record in records]

    def parse_bytes(
        self,
        *,
        content: bytes,
        marketplace_id: str,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> list[SettlementV2TransactionRecord]:
        text, _encoding = decode_report_content(content)
        return self.parse_text(
            text=text,
            marketplace_id=marketplace_id,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
        )

    def parse_text(
        self,
        *,
        text: str,
        marketplace_id: str,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> list[SettlementV2TransactionRecord]:
        delimiter = detect_report_delimiter(text)
        if delimiter is None:
            raise ValueError("Settlement report must be a delimited flat file")

        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        fieldnames = set(reader.fieldnames or [])
        missing_fields = sorted(SETTLEMENT_V2_REQUIRED_FIELDS - fieldnames)
        if missing_fields:
            raise ValueError(f"Missing required settlement report fields: {missing_fields}")

        current_summary: dict[str, str] = {}
        records: list[SettlementV2TransactionRecord] = []
        for raw_row in reader:
            row = {str(key): (value or "").strip() for key, value in raw_row.items() if key}
            if _looks_like_settlement_summary_row(row):
                current_summary = _summary_values_from_row(row)
            effective_row = _apply_summary_defaults(row=row, current_summary=current_summary)
            is_summary = _looks_like_settlement_summary_row(row)
            classification = classify_settlement_amount(
                transaction_type=effective_row.get("transaction-type"),
                amount_type=effective_row.get("amount-type"),
                amount_description=effective_row.get("amount-description"),
                is_settlement_summary=is_summary,
            )
            records.append(
                SettlementV2TransactionRecord(
                    marketplace_id=marketplace_id,
                    settlement_id=_empty_to_none(effective_row.get("settlement-id")),
                    settlement_start_date_raw=_empty_to_none(
                        effective_row.get("settlement-start-date")
                    ),
                    settlement_end_date_raw=_empty_to_none(
                        effective_row.get("settlement-end-date")
                    ),
                    deposit_date_raw=_empty_to_none(effective_row.get("deposit-date")),
                    total_amount=_parse_decimal(effective_row.get("total-amount")),
                    currency=_empty_to_none(effective_row.get("currency")),
                    is_settlement_summary=is_summary,
                    transaction_type=_empty_to_none(effective_row.get("transaction-type")),
                    order_id=_empty_to_none(effective_row.get("order-id")),
                    merchant_order_id=_empty_to_none(effective_row.get("merchant-order-id")),
                    adjustment_id=_empty_to_none(effective_row.get("adjustment-id")),
                    shipment_id=_empty_to_none(effective_row.get("shipment-id")),
                    marketplace_name=_empty_to_none(effective_row.get("marketplace-name")),
                    amount_type=_empty_to_none(effective_row.get("amount-type")),
                    amount_description=_empty_to_none(effective_row.get("amount-description")),
                    amount=_parse_decimal(effective_row.get("amount")),
                    amount_category=classification.amount_category,
                    profit_bucket=classification.profit_bucket,
                    fulfillment_id=_empty_to_none(effective_row.get("fulfillment-id")),
                    posted_date_raw=_empty_to_none(effective_row.get("posted-date")),
                    posted_date_time_raw=_empty_to_none(effective_row.get("posted-date-time")),
                    order_item_code=_empty_to_none(effective_row.get("order-item-code")),
                    merchant_order_item_id=_empty_to_none(
                        effective_row.get("merchant-order-item-id")
                    ),
                    merchant_adjustment_item_id=_empty_to_none(
                        effective_row.get("merchant-adjustment-item-id")
                    ),
                    seller_sku=_empty_to_none(effective_row.get("sku")),
                    quantity_purchased=_parse_int(effective_row.get("quantity-purchased")),
                    promotion_id=_empty_to_none(effective_row.get("promotion-id")),
                    source_system="sp_api_reports",
                    source_report_type=SETTLEMENT_V2_REPORT_TYPE,
                    source_report_id=source_report_id,
                    source_raw_file_path=source_raw_file_path,
                    source_row_hash=compute_source_row_hash(row),
                    raw_data=row,
                )
            )
        return records


def classify_settlement_amount(
    *,
    transaction_type: str | None,
    amount_type: str | None,
    amount_description: str | None,
    is_settlement_summary: bool = False,
) -> SettlementAmountClassification:
    """Classify a settlement amount into a first-pass profit bucket.

    This is intentionally conservative. It should help downstream review, but it
    must not be treated as final accounting logic until reconciled against real
    monthly reports and accountant feedback.
    """

    if is_settlement_summary:
        return SettlementAmountClassification("settlement_summary", "reconciliation")

    transaction = _normalize_token(transaction_type)
    amount_kind = _normalize_token(amount_type)
    description = _normalize_token(amount_description)

    if not transaction and not amount_kind and not description:
        return SettlementAmountClassification("unknown", "unknown")

    if amount_kind == "itemwithheldtax" or "marketplacefacilitatortax" in description:
        return SettlementAmountClassification("marketplace_facilitator_tax", "tax_passthrough")

    if description in {"tax", "shippingtax"}:
        return SettlementAmountClassification("sales_tax", "tax_passthrough")

    if amount_kind == "costofadvertising":
        return SettlementAmountClassification("advertising_fee", "advertising_cost")

    if amount_kind in {
        "couponperformancebasedfee",
        "couponparticipationfee",
    }:
        return SettlementAmountClassification("coupon_fee", "promotion_fee")

    if amount_kind in {"dealperformancebasedfee", "dealparticipationfee"}:
        return SettlementAmountClassification("deal_fee", "promotion_fee")

    if amount_kind == "fbainventoryreimbursement":
        if description == "compensatedclawback":
            return SettlementAmountClassification("reimbursement_clawback", "reimbursement")
        return SettlementAmountClassification("inventory_reimbursement", "reimbursement")

    if transaction == "liquidations":
        if amount_kind == "itemprice":
            return SettlementAmountClassification("liquidation_revenue", "liquidation")
        if amount_kind == "itemfees":
            return SettlementAmountClassification("liquidation_fee", "liquidation_fee")

    if "storagefee" in description:
        return SettlementAmountClassification("storage_fee", "fba_storage_fee")

    if "inboundplacementservicefee" in description:
        return SettlementAmountClassification("fba_inbound_placement_fee", "fba_fee")

    if "subscriptionfee" in description:
        return SettlementAmountClassification("subscription_fee", "amazon_fee")

    if description in {"payabletoamazon", "successfulcharge"}:
        return SettlementAmountClassification("settlement_transfer", "reconciliation")

    if amount_kind == "promotion":
        if transaction.startswith("refund"):
            return SettlementAmountClassification("promotion_refund_adjustment", "promotion_cost")
        return SettlementAmountClassification("promotion_discount", "promotion_cost")

    if amount_kind == "itemprice":
        if transaction.startswith("refund"):
            return SettlementAmountClassification("refund_revenue", "refund")
        if description == "shipping":
            return SettlementAmountClassification("shipping_revenue", "revenue")
        if description == "principal":
            return SettlementAmountClassification("product_sales", "revenue")
        if description == "restockingfee":
            return SettlementAmountClassification("restocking_fee", "refund")
        return SettlementAmountClassification("item_price", "revenue")

    if amount_kind == "itemfees":
        if description == "fbaperunitfulfillmentfee":
            return SettlementAmountClassification("fba_fulfillment_fee", "fba_fee")
        if description == "commission":
            if transaction.startswith("refund"):
                return SettlementAmountClassification("commission_refund", "amazon_fee_refund")
            return SettlementAmountClassification("referral_fee", "amazon_fee")
        if description == "refundcommission":
            return SettlementAmountClassification("refund_commission", "amazon_fee_refund")
        if description == "shippingchargeback":
            return SettlementAmountClassification("shipping_chargeback", "amazon_fee")
        return SettlementAmountClassification("item_fee", "amazon_fee")

    if amount_kind == "othertransaction" or transaction == "othertransaction":
        return SettlementAmountClassification("other_transaction", "other")

    if transaction in {"order_retrocharge", "refund_retrocharge"}:
        return SettlementAmountClassification("retrocharge", "tax_passthrough")

    return SettlementAmountClassification("unclassified", "unknown")


def compute_source_row_hash(row: dict[str, str]) -> str:
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _summary_values_from_row(row: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key in [
            "settlement-id",
            "settlement-start-date",
            "settlement-end-date",
            "deposit-date",
            "total-amount",
            "currency",
        ]
        if (value := (row.get(key) or "").strip())
    }


def _apply_summary_defaults(
    *,
    row: dict[str, str],
    current_summary: dict[str, str],
) -> dict[str, str]:
    effective_row = dict(row)
    for key, value in current_summary.items():
        if not effective_row.get(key):
            effective_row[key] = value
    return effective_row


def _looks_like_settlement_summary_row(row: dict[str, str]) -> bool:
    return bool(row.get("settlement-id")) and bool(
        row.get("total-amount") or row.get("currency")
    ) and not any(
        row.get(key)
        for key in [
            "transaction-type",
            "amount-type",
            "amount-description",
            "amount",
            "posted-date",
            "posted-date-time",
        ]
    )


def _normalize_token(value: str | None) -> str:
    return re_sub_non_alnum((value or "").strip().lower())


def re_sub_non_alnum(value: str) -> str:
    return "".join(character for character in value if character.isalnum() or character == "_")


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
    normalized = _normalize_decimal_string(value)
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def _normalize_decimal_string(value: str) -> str:
    normalized = value.strip().replace("$", "").replace("£", "").replace("€", "")
    normalized = normalized.replace(" ", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = "-" + normalized[1:-1]

    comma_index = normalized.rfind(",")
    dot_index = normalized.rfind(".")
    if comma_index >= 0 and dot_index >= 0:
        if comma_index > dot_index:
            return normalized.replace(".", "").replace(",", ".")
        return normalized.replace(",", "")
    if comma_index >= 0:
        fractional = normalized[comma_index + 1 :]
        if 1 <= len(fractional) <= 2:
            return normalized.replace(",", ".")
        return normalized.replace(",", "")
    return normalized
