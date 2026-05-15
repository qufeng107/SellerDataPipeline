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


def test_analyze_top_level_ads_json_array_returns_rows_and_source_system(
    tmp_path: Path,
) -> None:
    raw_file = tmp_path / "ads.json"
    raw_file.write_text(
        '[{"date":"2026-05-14","campaignId":123,"clicks":5,"cost":2.34}]',
        encoding="utf-8",
    )

    from seller_data_pipeline.sampling.report_analyzer import analyze_report_file

    analysis = analyze_report_file(
        raw_file_path=raw_file,
        report_type="spCampaigns",
        marketplace_id="1234567890",
        source_system="amazon_ads",
    )

    assert analysis.source_system == "amazon_ads"
    assert analysis.file_format == "json"
    assert analysis.row_count == 1
    assert "top-level array length = 1" in (analysis.notes or [])
    field_names = {field.source_field_name for field in analysis.fields}
    assert "[].campaignId" in field_names
    campaign_id_field = next(
        field for field in analysis.fields if field.source_field_name == "[].campaignId"
    )
    assert campaign_id_field.mapping_status == "mapped_candidate"

    markdown = render_report_analysis_markdown(analysis)
    assert "| source_system | `amazon_ads` |" in markdown


def test_ads_report_specific_notes_include_target_table_and_redact_keywords(
    tmp_path: Path,
) -> None:
    raw_file = tmp_path / "targeting.json"
    raw_file.write_text(
        '[{"date":"2026-05-14","campaignId":123,"keyword":"passport holder",'
        '"targeting":"passport holder","clicks":5,"cost":2.34}]',
        encoding="utf-8",
    )

    from seller_data_pipeline.sampling.report_analyzer import analyze_report_file

    analysis = analyze_report_file(
        raw_file_path=raw_file,
        report_type="spTargeting",
        marketplace_id="1234567890",
        source_system="amazon_ads",
    )
    markdown = render_report_analysis_markdown(analysis)

    assert "amazon_ads_sp_targeting_daily" in markdown
    assert "sampling_confirmed" in markdown
    assert "passport holder" not in markdown
    assert "<redacted:" in markdown


def test_ads_search_term_report_notes_are_sampling_confirmed_and_redacted(
    tmp_path: Path,
) -> None:
    raw_file = tmp_path / "search_term.json"
    raw_file.write_text(
        '[{"date":"2026-05-14","campaignId":123,"keyword":"passport holder",'
        '"targeting":"passport holder","searchTerm":"travel wallet",'
        '"clicks":5,"cost":2.34}]',
        encoding="utf-8",
    )

    from seller_data_pipeline.sampling.report_analyzer import analyze_report_file

    analysis = analyze_report_file(
        raw_file_path=raw_file,
        report_type="spSearchTerm",
        marketplace_id="1234567890",
        source_system="amazon_ads",
    )
    markdown = render_report_analysis_markdown(analysis)

    assert "amazon_ads_sp_search_term_daily" in markdown
    assert "sampling_confirmed" in markdown
    assert "passport holder" not in markdown
    assert "travel wallet" not in markdown
    assert "<redacted:" in markdown




def test_ads_advertised_product_report_notes_are_sampling_confirmed(
    tmp_path: Path,
) -> None:
    raw_file = tmp_path / "advertised_product.json"
    raw_file.write_text(
        '[{"date":"2026-05-15","campaignId":123,"adGroupId":456,'
        '"advertisedAsin":"B000000001","advertisedSku":"SKU-001",'
        '"impressions":448,"clicks":2,"cost":1.25}]',
        encoding="utf-8",
    )

    from seller_data_pipeline.sampling.report_analyzer import analyze_report_file

    analysis = analyze_report_file(
        raw_file_path=raw_file,
        report_type="spAdvertisedProduct",
        marketplace_id="3917953989967300",
        source_system="amazon_ads",
    )
    markdown = render_report_analysis_markdown(analysis)

    assert "amazon_ads_sp_advertised_product_daily" in markdown
    assert "sampling_confirmed" in markdown
    assert "B000000001" not in markdown
    assert "SKU-001" not in markdown
    assert "<redacted:" in markdown

def test_ads_empty_purchased_product_report_is_confirmed_empty(
    tmp_path: Path,
) -> None:
    raw_file = tmp_path / "purchased_product.json"
    raw_file.write_text("[]", encoding="utf-8")

    from seller_data_pipeline.sampling.report_analyzer import analyze_report_file

    analysis = analyze_report_file(
        raw_file_path=raw_file,
        report_type="spPurchasedProduct",
        marketplace_id="3917953989967300",
        source_system="amazon_ads",
    )
    markdown = render_report_analysis_markdown(analysis)

    assert analysis.row_count == 0
    assert "top-level array length = 0" in (analysis.notes or [])
    assert "amazon_ads_sp_purchased_product_daily" in markdown
    assert "sampling_confirmed_empty" in markdown
    assert "不是 API 或 parser 失败" in markdown

