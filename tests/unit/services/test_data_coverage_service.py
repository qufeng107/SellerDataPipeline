from __future__ import annotations

from datetime import UTC, date, datetime

from seller_data_pipeline.services.data_coverage_service import (
    DataCoverageAuditService,
    classify_coverage_status,
    render_coverage_markdown,
)


def test_classify_coverage_status() -> None:
    target_start = date(2026, 1, 1)

    assert (
        classify_coverage_status(
            row_count=0,
            dated_row_count=0,
            min_business_date=None,
            max_business_date=None,
            target_window_row_count=0,
            target_start_date=target_start,
        )
        == "no_rows"
    )
    assert (
        classify_coverage_status(
            row_count=2,
            dated_row_count=0,
            min_business_date=None,
            max_business_date=None,
            target_window_row_count=0,
            target_start_date=target_start,
        )
        == "no_business_dates"
    )
    assert (
        classify_coverage_status(
            row_count=2,
            dated_row_count=2,
            min_business_date=date(2025, 12, 1),
            max_business_date=date(2025, 12, 31),
            target_window_row_count=0,
            target_start_date=target_start,
        )
        == "outside_target_window"
    )
    assert (
        classify_coverage_status(
            row_count=2,
            dated_row_count=2,
            min_business_date=date(2026, 2, 1),
            max_business_date=date(2026, 5, 1),
            target_window_row_count=2,
            target_start_date=target_start,
        )
        == "starts_after_target_start"
    )
    assert (
        classify_coverage_status(
            row_count=2,
            dated_row_count=2,
            min_business_date=date(2026, 1, 1),
            max_business_date=date(2026, 5, 1),
            target_window_row_count=2,
            target_start_date=target_start,
        )
        == "has_target_window_data"
    )


def test_run_builds_coverage_result_and_status_counts() -> None:
    service = DataCoverageAuditService(repo=FakeCoverageRepo())

    result = service.run(
        marketplace_id="ATVPDKIKX0DER",
        target_start_date=date(2026, 1, 1),
        target_end_date=date(2026, 5, 18),
    )

    assert result.marketplace_id == "ATVPDKIKX0DER"
    assert result.status_counts == {
        "has_target_window_data": 1,
        "starts_after_target_start": 1,
    }
    assert result.coverage_rows[0].days_since_latest_business_date == 17
    assert result.coverage_rows[1].coverage_start_gap_days == 45
    assert result.report_request_rows[0].parsed_count == 1


def test_write_and_render_coverage_files(tmp_path) -> None:
    service = DataCoverageAuditService(repo=FakeCoverageRepo())

    result = service.run(
        marketplace_id="ATVPDKIKX0DER",
        target_start_date=date(2026, 1, 1),
        target_end_date=date(2026, 5, 18),
        output_root=tmp_path,
    )

    assert set(result.output_files) == {
        "json",
        "markdown",
        "coverage_csv",
        "report_request_csv",
    }
    for path in result.output_files.values():
        assert tmp_path in __import__("pathlib").Path(path).parents
        assert __import__("pathlib").Path(path).exists()

    markdown = render_coverage_markdown(result)
    assert "Data Coverage Audit" in markdown
    assert "Settlement transaction" in markdown
    assert "Report request coverage" in markdown


class FakeCoverageRepo:
    def fetch_core_coverage_rows(
        self,
        *,
        marketplace_id: str,
        target_start_date: date,
        target_end_date: date,
    ) -> list[dict[str, object]]:
        assert marketplace_id == "ATVPDKIKX0DER"
        assert target_start_date == date(2026, 1, 1)
        assert target_end_date == date(2026, 5, 18)
        return [
            {
                "data_domain": "Settlement transaction",
                "source_table": "amazon_settlement_transaction",
                "business_date_semantics": "posted_date",
                "row_count": 10,
                "dated_row_count": 10,
                "min_business_date": date(2026, 1, 1),
                "max_business_date": date(2026, 5, 1),
                "distinct_business_dates": 5,
                "distinct_entity_count": 2,
                "target_window_row_count": 10,
                "target_min_business_date": date(2026, 1, 1),
                "target_max_business_date": date(2026, 5, 1),
                "latest_created_at": datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
                "latest_updated_at": datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
                "notes": "Financial source of truth.",
            },
            {
                "data_domain": "Orders",
                "source_table": "amazon_order_item",
                "business_date_semantics": "purchase_date",
                "row_count": 4,
                "dated_row_count": 4,
                "min_business_date": date(2026, 2, 15),
                "max_business_date": date(2026, 5, 10),
                "distinct_business_dates": 4,
                "distinct_entity_count": 1,
                "target_window_row_count": 4,
                "target_min_business_date": date(2026, 2, 15),
                "target_max_business_date": date(2026, 5, 10),
                "latest_created_at": datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
                "latest_updated_at": datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
                "notes": "Operational source.",
            },
        ]

    def fetch_report_request_coverage_rows(
        self,
        *,
        marketplace_id: str,
        target_start_date: date,
        target_end_date: date,
    ) -> list[dict[str, object]]:
        return [
            {
                "source_system": "sp_api_reports",
                "report_type": "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2",
                "request_count": 1,
                "done_count": 1,
                "downloaded_count": 1,
                "parsed_count": 1,
                "min_data_start_date": date(2026, 1, 1),
                "max_data_end_date": date(2026, 5, 18),
                "target_overlap_request_count": 1,
                "latest_requested_at": datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
                "latest_downloaded_at": datetime(2026, 5, 18, 12, 1, tzinfo=UTC),
                "latest_parsed_at": datetime(2026, 5, 18, 12, 2, tzinfo=UTC),
            }
        ]
