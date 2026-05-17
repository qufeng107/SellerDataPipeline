from __future__ import annotations

from seller_data_pipeline.parsers.amazon.ads_report_parser import AdsReportParser


def test_ads_report_parser_normalizes_common_sp_fields() -> None:
    parser = AdsReportParser()

    records = parser.parse_text(
        text=(
            '[{"date":"2026-05-14","campaignId":123,"campaignName":"Campaign A",'
            '"campaignStatus":"ENABLED","adGroupId":456,"keywordId":789,'
            '"keyword":"passport holder","matchType":"EXACT",'
            '"impressions":100,"clicks":5,"cost":2.34,"sales7d":"20.50",'
            '"purchases7d":1,"unitsSoldClicks7d":1}]'
        ),
        profile_id="111",
        report_type_id="spTargeting",
        source_report_id="ads-report-1",
        source_raw_file_path="reports/raw/amazon_ads/111/spTargeting/report.json",
    )

    assert len(records) == 1
    record = records[0]
    assert record.source_system == "amazon_ads"
    assert record.profile_id == "111"
    assert record.report_type_id == "spTargeting"
    assert record.campaign_id == "123"
    assert record.keyword == "passport holder"
    assert record.clicks == 5
    assert str(record.cost) == "2.34"
    assert str(record.sales_7d) == "20.50"
    assert record.source_report_id == "ads-report-1"
    assert record.source_row_hash
    assert record.raw_data["campaignName"] == "Campaign A"


def test_ads_report_parser_accepts_object_with_rows_key() -> None:
    records = AdsReportParser().parse_text(
        text='{"rows":[{"date":"2026-05-14","campaignId":"1","clicks":2}]}',
        profile_id="111",
        report_type_id="spCampaigns",
    )

    assert len(records) == 1
    assert records[0].campaign_id == "1"
    assert records[0].clicks == 2


def test_ads_report_parser_normalizes_advertised_product_fields() -> None:
    records = AdsReportParser().parse_text(
        text=(
            '[{"date":"2026-05-15","campaignId":123,"campaignName":"Campaign A",'
            '"adGroupId":456,"adGroupName":"Ad Group A",'
            '"advertisedAsin":"B000000001","advertisedSku":"SKU-001",'
            '"impressions":448,"clicks":2,"cost":"1.25",'
            '"sales7d":"0","purchases7d":0,"unitsSoldClicks7d":0}]'
        ),
        profile_id="3917953989967300",
        report_type_id="spAdvertisedProduct",
    )

    assert len(records) == 1
    record = records[0]
    assert record.report_type_id == "spAdvertisedProduct"
    assert record.advertised_asin == "B000000001"
    assert record.advertised_sku == "SKU-001"
    assert record.ad_group_id == "456"
    assert record.impressions == 448
    assert record.clicks == 2
    assert str(record.cost) == "1.25"


def test_ads_report_parser_accepts_empty_array() -> None:
    records = AdsReportParser().parse_text(
        text="[]",
        profile_id="3917953989967300",
        report_type_id="spPurchasedProduct",
    )

    assert records == []
