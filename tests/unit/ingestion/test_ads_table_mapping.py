from __future__ import annotations

from seller_data_pipeline.ingestion.ads_table_mapping import (
    compute_business_key_hash,
    get_ads_target_table_spec,
    map_ads_record_to_table_row,
)
from seller_data_pipeline.parsers.amazon.ads_report_parser import AdsReportParser


def test_ads_campaign_mapping_builds_db_ready_row() -> None:
    spec = get_ads_target_table_spec("spCampaigns")
    assert spec is not None
    record = AdsReportParser().parse_text(
        text=(
            '[{"date":"2026-05-12","campaignId":123,"campaignName":"Campaign A",'
            '"campaignStatus":"ENABLED","impressions":10,"clicks":2,"cost":"1.23",'
            '"sales7d":"9.99","purchases7d":1,"unitsSoldClicks7d":1}]'
        ),
        profile_id="3917953989967300",
        report_type_id="spCampaigns",
        source_report_id="ads-report-1",
        source_raw_file_path="reports/raw/amazon_ads/391/spCampaigns/report.json",
    )[0]

    row = map_ads_record_to_table_row(
        record=record,
        table_spec=spec,
        marketplace_id="ATVPDKIKX0DER",
    )

    assert row["profile_id"] == "3917953989967300"
    assert row["marketplace_id"] == "ATVPDKIKX0DER"
    assert row["campaign_id"] == "123"
    assert row["cost"] == "1.23"
    assert row["business_key_hash"]
    assert "Campaign A" in row["raw_data"]
    assert set(row) == set(spec.table_columns)


def test_ads_business_key_hash_is_stable_and_table_scoped() -> None:
    fields = ("profile_id", "report_date", "campaign_id")
    row = {"profile_id": "1", "report_date": "2026-05-12", "campaign_id": "123"}

    first = compute_business_key_hash(
        target_table="amazon_ads_sp_campaign_daily",
        business_key_fields=fields,
        row=row,
    )
    second = compute_business_key_hash(
        target_table="amazon_ads_sp_campaign_daily",
        business_key_fields=fields,
        row=dict(reversed(list(row.items()))),
    )
    other_table = compute_business_key_hash(
        target_table="other_table",
        business_key_fields=fields,
        row=row,
    )

    assert first == second
    assert first != other_table


def test_purchased_product_mapping_is_not_table_ready_until_non_empty_sample() -> None:
    spec = get_ads_target_table_spec("spPurchasedProduct")

    assert spec is not None
    assert spec.table_ready is False
