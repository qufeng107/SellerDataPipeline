from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from seller_data_pipeline.parsers.amazon.flat_file_utils import (
    AmazonFlatFileParser,
    compute_source_row_hash,
    empty_to_none,
    parse_bool,
    parse_decimal,
    parse_int,
    serialize_decimals,
)

RETURNS_BY_RETURN_DATE_REPORT_TYPE = "GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE"

RETURNS_REQUIRED_FIELDS = {
    "Order ID",
    "Order date",
    "Return request date",
    "Return request status",
    "Amazon RMA ID",
    "Currency code",
    "ASIN",
    "Merchant SKU",
    "Item Name",
    "Return quantity",
    "Return Reason",
    "Resolution",
    "Refunded Amount",
    "Order Item ID",
}

_DECIMAL_FIELDS = {
    "label_cost",
    "order_amount",
    "safe_t_claim_reimbursement_amount",
    "refunded_amount",
}


@dataclass(frozen=True)
class ReturnsByReturnDateRecord:
    marketplace_id: str
    order_id: str | None
    order_date_raw: str | None
    return_request_date_raw: str | None
    return_request_status: str | None
    amazon_rma_id: str | None
    merchant_rma_id: str | None
    label_type: str | None
    label_cost: Decimal | None
    currency_code: str | None
    return_carrier: str | None
    tracking_id: str | None
    label_to_be_paid_by: str | None
    a_to_z_claim: bool | None
    is_prime: bool | None
    asin: str | None
    seller_sku: str | None
    item_name: str | None
    return_quantity: int | None
    return_reason: str | None
    in_policy: bool | None
    return_type: str | None
    resolution: str | None
    invoice_number: str | None
    return_delivery_date_raw: str | None
    order_amount: Decimal | None
    order_quantity: int | None
    safe_t_action_reason: str | None
    safe_t_claim_id: str | None
    safe_t_claim_state: str | None
    safe_t_claim_creation_time_raw: str | None
    safe_t_claim_reimbursement_amount: Decimal | None
    refunded_amount: Decimal | None
    order_item_id: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return serialize_decimals(payload, _DECIMAL_FIELDS)


class ReturnsByReturnDateParser(AmazonFlatFileParser):
    """Parser for GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE reports."""

    report_type = RETURNS_BY_RETURN_DATE_REPORT_TYPE
    required_fields = RETURNS_REQUIRED_FIELDS

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> ReturnsByReturnDateRecord:
        return ReturnsByReturnDateRecord(
            marketplace_id=marketplace_id,
            order_id=empty_to_none(row.get("Order ID")),
            order_date_raw=empty_to_none(row.get("Order date")),
            return_request_date_raw=empty_to_none(row.get("Return request date")),
            return_request_status=empty_to_none(row.get("Return request status")),
            amazon_rma_id=empty_to_none(row.get("Amazon RMA ID")),
            merchant_rma_id=empty_to_none(row.get("Merchant RMA ID")),
            label_type=empty_to_none(row.get("Label type")),
            label_cost=parse_decimal(row.get("Label cost")),
            currency_code=empty_to_none(row.get("Currency code")),
            return_carrier=empty_to_none(row.get("Return carrier")),
            tracking_id=empty_to_none(row.get("Tracking ID")),
            label_to_be_paid_by=empty_to_none(row.get("Label to be paid by")),
            a_to_z_claim=parse_bool(row.get("A-to-Z Claim")),
            is_prime=parse_bool(row.get("Is prime")),
            asin=empty_to_none(row.get("ASIN")),
            seller_sku=empty_to_none(row.get("Merchant SKU")),
            item_name=empty_to_none(row.get("Item Name")),
            return_quantity=parse_int(row.get("Return quantity")),
            return_reason=empty_to_none(row.get("Return Reason")),
            in_policy=parse_bool(row.get("In policy")),
            return_type=empty_to_none(row.get("Return type")),
            resolution=empty_to_none(row.get("Resolution")),
            invoice_number=empty_to_none(row.get("Invoice number")),
            return_delivery_date_raw=empty_to_none(row.get("Return delivery date")),
            order_amount=parse_decimal(row.get("Order Amount")),
            order_quantity=parse_int(row.get("Order quantity")),
            safe_t_action_reason=empty_to_none(row.get("SafeT Action reason")),
            safe_t_claim_id=empty_to_none(row.get("SafeT claim id")),
            safe_t_claim_state=empty_to_none(row.get("SafeT claim state")),
            safe_t_claim_creation_time_raw=empty_to_none(row.get("SafeT claim creation time")),
            safe_t_claim_reimbursement_amount=parse_decimal(
                row.get("SafeT claim reimbursement amount")
            ),
            refunded_amount=parse_decimal(row.get("Refunded Amount")),
            order_item_id=empty_to_none(row.get("Order Item ID")),
            source_system="sp_api_reports",
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )
