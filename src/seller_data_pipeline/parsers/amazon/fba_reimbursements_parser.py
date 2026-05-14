from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from seller_data_pipeline.parsers.amazon.flat_file_utils import (
    AmazonFlatFileParser,
    compute_source_row_hash,
    empty_to_none,
    parse_decimal,
    parse_int,
    serialize_decimals,
)

FBA_REIMBURSEMENTS_REPORT_TYPE = "GET_FBA_REIMBURSEMENTS_DATA"

FBA_REIMBURSEMENTS_REQUIRED_FIELDS = {
    "approval-date",
    "reimbursement-id",
    "case-id",
    "amazon-order-id",
    "reason",
    "sku",
    "fnsku",
    "asin",
    "product-name",
    "condition",
    "currency-unit",
    "amount-per-unit",
    "amount-total",
    "quantity-reimbursed-cash",
    "quantity-reimbursed-inventory",
    "quantity-reimbursed-total",
    "original-reimbursement-id",
    "original-reimbursement-type",
}

_DECIMAL_FIELDS = {"amount_per_unit", "amount_total"}


@dataclass(frozen=True)
class FbaReimbursementRecord:
    marketplace_id: str
    approval_date_raw: str | None
    reimbursement_id: str | None
    case_id: str | None
    amazon_order_id: str | None
    reason: str | None
    seller_sku: str | None
    fnsku: str | None
    asin: str | None
    product_name: str | None
    condition: str | None
    currency: str | None
    amount_per_unit: Decimal | None
    amount_total: Decimal | None
    quantity_reimbursed_cash: int | None
    quantity_reimbursed_inventory: int | None
    quantity_reimbursed_total: int | None
    original_reimbursement_id: str | None
    original_reimbursement_type: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return serialize_decimals(payload, _DECIMAL_FIELDS)


class FbaReimbursementsParser(AmazonFlatFileParser):
    """Parser for GET_FBA_REIMBURSEMENTS_DATA reports."""

    report_type = FBA_REIMBURSEMENTS_REPORT_TYPE
    required_fields = FBA_REIMBURSEMENTS_REQUIRED_FIELDS

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> FbaReimbursementRecord:
        return FbaReimbursementRecord(
            marketplace_id=marketplace_id,
            approval_date_raw=empty_to_none(row.get("approval-date")),
            reimbursement_id=empty_to_none(row.get("reimbursement-id")),
            case_id=empty_to_none(row.get("case-id")),
            amazon_order_id=empty_to_none(row.get("amazon-order-id")),
            reason=empty_to_none(row.get("reason")),
            seller_sku=empty_to_none(row.get("sku")),
            fnsku=empty_to_none(row.get("fnsku")),
            asin=empty_to_none(row.get("asin")),
            product_name=empty_to_none(row.get("product-name")),
            condition=empty_to_none(row.get("condition")),
            currency=empty_to_none(row.get("currency-unit")),
            amount_per_unit=parse_decimal(row.get("amount-per-unit")),
            amount_total=parse_decimal(row.get("amount-total")),
            quantity_reimbursed_cash=parse_int(row.get("quantity-reimbursed-cash")),
            quantity_reimbursed_inventory=parse_int(row.get("quantity-reimbursed-inventory")),
            quantity_reimbursed_total=parse_int(row.get("quantity-reimbursed-total")),
            original_reimbursement_id=empty_to_none(row.get("original-reimbursement-id")),
            original_reimbursement_type=empty_to_none(row.get("original-reimbursement-type")),
            source_system="sp_api_reports",
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )
