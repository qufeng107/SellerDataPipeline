from __future__ import annotations

from seller_data_pipeline.sampling.raw_report_files import preview_report_bytes


def test_preview_report_bytes_detects_tsv_header_and_rows() -> None:
    preview = preview_report_bytes(b"sku\tprice\nABC\t9.99\nDEF\t8.99\n")

    assert preview.delimiter == "\t"
    assert preview.header == ["sku", "price"]
    assert preview.sample_rows[0] == {"sku": "ABC", "price": "9.99"}
    assert preview.row_count_previewed == 2


def test_preview_report_bytes_detects_csv_header_and_rows() -> None:
    preview = preview_report_bytes(b"sku,price\nABC,9.99\n")

    assert preview.delimiter == ","
    assert preview.header == ["sku", "price"]
    assert preview.sample_rows == [{"sku": "ABC", "price": "9.99"}]
