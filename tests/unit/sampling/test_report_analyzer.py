from __future__ import annotations

from pathlib import Path

from seller_data_pipeline.sampling.report_analyzer import (
    analyze_delimited_report_file,
    render_report_analysis_markdown,
)


def test_analyze_delimited_report_file_returns_field_stats(tmp_path: Path) -> None:
    raw_file = tmp_path / "listing.txt"
    raw_file.write_text(
        "seller-sku\tprice\tstatus\tquantity\n"
        "SKU-1\t25.50\tActive\t\n"
        "SKU-2\t\tInactive\t3\n",
        encoding="utf-8",
    )

    analysis = analyze_delimited_report_file(
        raw_file_path=raw_file,
        report_type="GET_MERCHANT_LISTINGS_ALL_DATA",
        marketplace_id="ATVPDKIKX0DER",
    )

    assert analysis.row_count == 2
    assert analysis.column_count == 4
    assert analysis.fields[0].source_field_name == "seller-sku"
    assert analysis.fields[0].sample_values == ["<redacted:5 chars>", "<redacted:5 chars>"]
    assert analysis.fields[1].data_type_suggestion == "decimal"
    assert analysis.fields[3].non_empty_count == 1


def test_render_report_analysis_markdown_includes_summary(tmp_path: Path) -> None:
    raw_file = tmp_path / "listing.txt"
    raw_file.write_text("status\tprice\nActive\t25\n", encoding="utf-8")
    analysis = analyze_delimited_report_file(
        raw_file_path=raw_file,
        report_type="GET_MERCHANT_LISTINGS_ALL_DATA",
        marketplace_id="ATVPDKIKX0DER",
    )

    markdown = render_report_analysis_markdown(analysis)

    assert "GET_MERCHANT_LISTINGS_ALL_DATA 字段取样记录" in markdown
    assert "`status`" in markdown
    assert "amazon_listing_snapshot" in markdown
