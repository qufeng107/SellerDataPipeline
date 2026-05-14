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


def test_render_inventory_report_analysis_markdown_includes_inventory_table(
    tmp_path: Path,
) -> None:
    raw_file = tmp_path / "inventory.txt"
    raw_file.write_text(
        "sku\tafn-fulfillable-quantity\tafn-total-quantity\n"
        "SKU-1\t3\t4\n",
        encoding="utf-8",
    )
    analysis = analyze_delimited_report_file(
        raw_file_path=raw_file,
        report_type="GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA",
        marketplace_id="ATVPDKIKX0DER",
    )

    markdown = render_report_analysis_markdown(analysis)

    assert "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA 字段取样记录" in markdown
    assert analysis.fields[1].data_type_suggestion == "integer"
    assert "amazon_inventory_daily" in markdown


def test_analyze_json_sales_report_returns_flattened_paths(tmp_path: Path) -> None:
    raw_file = tmp_path / "sales.json"
    raw_file.write_text(
        '{'
        '"reportSpecification": {'
        '"reportType": "GET_SALES_AND_TRAFFIC_REPORT",'
        '"reportOptions": {"dateGranularity": "DAY", "asinGranularity": "PARENT"},'
        '"dataStartTime": "2026-05-14",'
        '"dataEndTime": "2026-05-14",'
        '"marketplaceIds": ["ATVPDKIKX0DER"]'
        '},'
        '"salesAndTrafficByDate": [{'
        '"date": "2026-05-14",'
        '"salesByDate": {'
        '"orderedProductSales": {"amount": 12.34, "currencyCode": "USD"},'
        '"unitsOrdered": 2'
        '},'
        '"trafficByDate": {"sessions": 10, "unitSessionPercentage": 20.0}'
        '}],'
        '"salesAndTrafficByAsin": [{'
        '"parentAsin": "B000000001",'
        '"salesByAsin": {'
        '"orderedProductSales": {"amount": 12.34, "currencyCode": "USD"},'
        '"unitsOrdered": 2'
        '},'
        '"trafficByAsin": {"sessions": 10, "unitSessionPercentage": 20.0}'
        '}]'
        '}',
        encoding="utf-8",
    )

    from seller_data_pipeline.sampling.report_analyzer import analyze_report_file

    analysis = analyze_report_file(
        raw_file_path=raw_file,
        report_type="GET_SALES_AND_TRAFFIC_REPORT",
        marketplace_id="ATVPDKIKX0DER",
    )

    field_names = {field.source_field_name for field in analysis.fields}
    assert analysis.file_format == "json"
    assert analysis.row_count == 1
    assert "salesAndTrafficByDate[].salesByDate.unitsOrdered" in field_names
    assert "salesAndTrafficByAsin[].parentAsin" in field_names
    asin_field = next(
        field
        for field in analysis.fields
        if field.source_field_name == "salesAndTrafficByAsin[].parentAsin"
    )
    assert asin_field.mapping_status == "mapped_candidate"

    markdown = render_report_analysis_markdown(analysis)
    assert "amazon_sales_traffic_daily" in markdown
    assert "amazon_sales_traffic_asin_daily" in markdown
    assert "JSON 格式" in markdown
    assert "salesAndTrafficByAsin` 1 行" in markdown
