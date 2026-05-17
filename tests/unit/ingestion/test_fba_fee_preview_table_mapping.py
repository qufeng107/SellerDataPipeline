from __future__ import annotations

from seller_data_pipeline.ingestion.fba_fee_preview_table_mapping import (
    FBA_FEE_PREVIEW_TARGET_TABLE_SPEC,
    map_fba_fee_preview_record_to_table_row,
)
from seller_data_pipeline.parsers.amazon.fba_estimated_fees_parser import FbaEstimatedFeesParser

FBA_FEE_PREVIEW_CONTENT = (
    "sku\tfnsku\tasin\tamazon-store\tproduct-name\tproduct-group\tbrand\tfulfilled-by\t"
    "your-price\tsales-price\tlongest-side\tmedian-side\tshortest-side\tlength-and-girth\t"
    "unit-of-dimension\titem-package-weight\tunit-of-weight\tproduct-size-tier\tcurrency\t"
    "estimated-fee-total\testimated-referral-fee-per-unit\testimated-variable-closing-fee\t"
    "estimated-order-handling-fee-per-order\testimated-pick-pack-fee-per-unit\t"
    "estimated-weight-handling-fee-per-unit\texpected-fulfillment-fee-per-unit\t"
    "estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)\t"
    "estimated-future-order-handling-fee-per-order\testimated-future-pick-pack-fee-per-unit\t"
    "estimated-future-weight-handling-fee-per-unit\texpected-future-fulfillment-fee-per-unit\n"
    "SKU-1\tFNSKU-1\tB000TEST\tUS\tTravel Wallet\tLuggage\tChynotopia\tAmazon\t"
    "25.00\t25.00\t7.72\t6.54\t1.22\t23.24\tinches\t0.18\tpounds\t"
    "UsLargeStandardSize\tUSD\t7.80\t3.75\t0.00\t--\t--\t--\t4.05\t--\t--\t--\t--\t--\n"
)


def test_map_fba_fee_preview_record_to_table_row_is_db_ready() -> None:
    record = FbaEstimatedFeesParser().parse_bytes(
        content=FBA_FEE_PREVIEW_CONTENT.encode("utf-8"),
        marketplace_id="ATVPDKIKX0DER",
        source_report_id="fba-fee-preview-report-1",
        source_raw_file_path="reports/raw/fba-fee-preview-report-1.txt",
    )[0]

    row = map_fba_fee_preview_record_to_table_row(record, source_row_index=1)

    assert tuple(row) == FBA_FEE_PREVIEW_TARGET_TABLE_SPEC.table_columns
    assert row["marketplace_id"] == "ATVPDKIKX0DER"
    assert row["seller_sku"] == "SKU-1"
    assert row["fnsku"] == "FNSKU-1"
    assert row["asin"] == "B000TEST"
    assert row["amazon_store"] == "US"
    assert row["your_price"] == "25.00"
    assert row["estimated_fee_total"] == "7.80"
    assert row["expected_fulfillment_fee_per_unit"] == "4.05"
    assert row["estimated_order_handling_fee_per_order"] is None
    assert row["source_row_index"] == 1
    assert row["business_key_hash"]
    assert isinstance(row["raw_data"], str)
