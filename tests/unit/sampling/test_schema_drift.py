from __future__ import annotations

from seller_data_pipeline.sampling.report_analyzer import analyze_json_report_text
from seller_data_pipeline.sampling.schema_drift import (
    ExpectedReportSchema,
    build_ads_expected_schema,
    normalize_field_name,
    validate_report_schema,
)


def _analyze_ads_json(text: str, report_type: str = "spCampaigns"):
    return analyze_json_report_text(
        text=text,
        raw_file_path="sample.json",
        report_type=report_type,
        marketplace_id="123",
        source_system="amazon_ads",
        encoding="utf-8",
        sample_value_limit=3,
        redact_sample_values=True,
    )


def test_normalize_field_name_strips_common_json_row_prefix() -> None:
    assert normalize_field_name("[].campaignId") == "campaignId"
    assert normalize_field_name("rows[].campaignId") == "campaignId"
    field_name = "reportSpecification.reportType"
    assert normalize_field_name(field_name) == field_name


def test_validate_ads_schema_ok_when_observed_fields_match_plan() -> None:
    analysis = _analyze_ads_json(
        """
        [{
          "date":"2026-05-15",
          "campaignId":"1",
          "campaignName":"Campaign",
          "campaignStatus":"ENABLED",
          "impressions":10,
          "clicks":1,
          "cost":0.5,
          "sales7d":2.0,
          "purchases7d":1,
          "unitsSoldClicks7d":1
        }]
        """
    )

    result = validate_report_schema(
        analysis=analysis,
        expected_schema=build_ads_expected_schema("spCampaigns"),
    )

    assert result.status == "ok"
    assert not result.requires_review
    assert result.missing_fields == ()
    assert result.new_fields == ()


def test_validate_ads_schema_detects_new_fields() -> None:
    analysis = _analyze_ads_json(
        """
        [{
          "date":"2026-05-15",
          "campaignId":"1",
          "campaignName":"Campaign",
          "campaignStatus":"ENABLED",
          "impressions":10,
          "clicks":1,
          "cost":0.5,
          "sales7d":2.0,
          "purchases7d":1,
          "unitsSoldClicks7d":1,
          "newMetric":99
        }]
        """
    )

    result = validate_report_schema(
        analysis=analysis,
        expected_schema=build_ads_expected_schema("spCampaigns"),
    )

    assert result.status == "new_fields"
    assert result.severity == "warning"
    assert not result.requires_review
    assert result.new_fields == ("newMetric",)


def test_validate_ads_schema_detects_missing_fields() -> None:
    analysis = _analyze_ads_json('[{"campaignId":"1","clicks":2}]')

    result = validate_report_schema(
        analysis=analysis,
        expected_schema=build_ads_expected_schema("spCampaigns"),
    )

    assert result.status == "missing_fields"
    assert result.requires_review
    assert "date" in result.missing_fields
    assert "campaignId" not in result.missing_fields


def test_validate_ads_schema_marks_empty_report_without_review() -> None:
    analysis = _analyze_ads_json("[]", report_type="spPurchasedProduct")

    result = validate_report_schema(
        analysis=analysis,
        expected_schema=build_ads_expected_schema("spPurchasedProduct"),
    )

    assert result.status == "empty_report"
    assert not result.requires_review
    assert result.row_count == 0
    assert result.observed_fields == ()


def test_validate_schema_blocks_required_missing_plus_new_fields() -> None:
    analysis = _analyze_ads_json('[{"campaignId":"1","newMetric":99}]')
    expected = ExpectedReportSchema(
        source_system="amazon_ads",
        report_type="spCampaigns",
        expected_fields=("campaignId", "date"),
        required_fields=("campaignId", "date"),
    )

    result = validate_report_schema(analysis=analysis, expected_schema=expected)

    assert result.status == "schema_drift"
    assert result.severity == "error"
    assert result.requires_review
    assert result.missing_fields == ("date",)
    assert result.new_fields == ("newMetric",)


def test_validate_schema_allows_known_optional_field_to_be_absent() -> None:
    analysis = _analyze_ads_json('[{"campaignId":"1"}]')
    expected = ExpectedReportSchema(
        source_system="amazon_ads",
        report_type="spCampaigns",
        expected_fields=("campaignId", "optionalMetric"),
        required_fields=("campaignId",),
    )

    result = validate_report_schema(analysis=analysis, expected_schema=expected)

    assert result.status == "ok"
    assert not result.requires_review
    assert result.missing_fields == ()
    assert "optional" in result.message.lower()


def test_validate_schema_blocks_unexpected_empty_report() -> None:
    analysis = _analyze_ads_json("[]")
    expected = ExpectedReportSchema(
        source_system="amazon_ads",
        report_type="spCampaigns",
        expected_fields=("campaignId",),
        required_fields=("campaignId",),
        allow_empty_report=False,
    )

    result = validate_report_schema(analysis=analysis, expected_schema=expected)

    assert result.status == "empty_report_unexpected"
    assert result.severity == "error"
    assert result.requires_review
