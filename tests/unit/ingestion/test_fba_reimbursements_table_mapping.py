from __future__ import annotations

from seller_data_pipeline.ingestion.fba_reimbursements_table_mapping import (
    FBA_REIMBURSEMENTS_TARGET_TABLE_SPEC,
    map_fba_reimbursement_record_to_table_row,
)
from seller_data_pipeline.parsers.amazon.fba_reimbursements_parser import FbaReimbursementsParser

FBA_REIMBURSEMENTS_CONTENT = (
    "approval-date\treimbursement-id\tcase-id\tamazon-order-id\treason\tsku\tfnsku\tasin\t"
    "product-name\tcondition\tcurrency-unit\tamount-per-unit\tamount-total\t"
    "quantity-reimbursed-cash\tquantity-reimbursed-inventory\tquantity-reimbursed-total\t"
    "original-reimbursement-id\toriginal-reimbursement-type\n"
    "2026-05-10T01:02:03+00:00\tR-1\tCASE-1\tORDER-1\tCustomerReturn\tSKU-1\tFNSKU-1\t"
    "B000TEST\tTravel Wallet\tNewItem\tUSD\t10.00\t20.00\t2\t0\t2\t\t\n"
)


def test_map_fba_reimbursement_record_to_table_row_is_db_ready() -> None:
    record = FbaReimbursementsParser().parse_bytes(
        content=FBA_REIMBURSEMENTS_CONTENT.encode("utf-8"),
        marketplace_id="ATVPDKIKX0DER",
        source_report_id="fba-reimbursements-report-1",
        source_raw_file_path="reports/raw/fba-reimbursements-report-1.txt",
    )[0]

    row = map_fba_reimbursement_record_to_table_row(record, source_row_index=1)

    assert tuple(row) == FBA_REIMBURSEMENTS_TARGET_TABLE_SPEC.table_columns
    assert row["marketplace_id"] == "ATVPDKIKX0DER"
    assert row["reimbursement_id"] == "R-1"
    assert row["case_id"] == "CASE-1"
    assert row["amazon_order_id"] == "ORDER-1"
    assert row["seller_sku"] == "SKU-1"
    assert row["fnsku"] == "FNSKU-1"
    assert row["asin"] == "B000TEST"
    assert row["amount_per_unit"] == "10.00"
    assert row["amount_total"] == "20.00"
    assert row["quantity_reimbursed_total"] == 2
    assert row["source_row_index"] == 1
    assert row["business_key_hash"]
    assert isinstance(row["raw_data"], str)
