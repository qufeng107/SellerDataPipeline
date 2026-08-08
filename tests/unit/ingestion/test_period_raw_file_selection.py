from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from seller_data_pipeline.ingestion.period_raw_file_selection import (
    select_ads_period_raw_files,
    select_sp_api_period_raw_files,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_sp_api_period_selection_covers_all_chunks_and_dedupes_latest(tmp_path: Path) -> None:
    sampling = tmp_path / "runtime" / "sampling"
    raw_root = tmp_path / "reports" / "raw"
    intervals = [
        ("r1", "2026-06-01T00:00:00Z", "2026-06-15T00:00:00Z", "2026-08-01T00:00:00Z"),
        ("r2-old", "2026-06-15T00:00:00Z", "2026-06-29T00:00:00Z", "2026-08-01T00:00:00Z"),
        ("r2", "2026-06-15T00:00:00Z", "2026-06-29T00:00:00Z", "2026-08-02T00:00:00Z"),
        ("r3", "2026-06-29T00:00:00Z", "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z"),
    ]
    for report_id, start, end, updated in intervals:
        raw = raw_root / f"{report_id}.txt"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text("x", encoding="utf-8")
        _write_json(
            sampling / "report_requests" / f"{report_id}.json",
            {
                "report_id": report_id,
                "report_type": "GET_SALES_AND_TRAFFIC_REPORT",
                "marketplace_ids": ["ATVPDKIKX0DER"],
                "data_start_time": start,
                "data_end_time": end,
                "processing_status": "DONE",
                "download_status": "DOWNLOADED",
                "raw_file_path": str(raw),
                "updated_at_utc": updated,
            },
        )

    result = select_sp_api_period_raw_files(
        sampling_root=sampling,
        marketplace_id="ATVPDKIKX0DER",
        report_type="GET_SALES_AND_TRAFFIC_REPORT",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert result.coverage_complete is True
    assert result.missing_ranges == ()
    assert [item.report_id for item in result.files] == ["r1", "r2", "r3"]


def test_sp_api_period_selection_fails_closed_on_gap(tmp_path: Path) -> None:
    sampling = tmp_path / "runtime" / "sampling"
    raw = tmp_path / "r1.txt"
    raw.write_text("x", encoding="utf-8")
    _write_json(
        sampling / "report_requests" / "r1.json",
        {
            "report_id": "r1",
            "report_type": "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL",
            "marketplace_ids": ["ATVPDKIKX0DER"],
            "data_start_time": "2026-06-01T00:00:00Z",
            "data_end_time": "2026-06-15T00:00:00Z",
            "processing_status": "DONE",
            "download_status": "DOWNLOADED",
            "raw_file_path": str(raw),
        },
    )

    result = select_sp_api_period_raw_files(
        sampling_root=sampling,
        marketplace_id="ATVPDKIKX0DER",
        report_type="GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert result.coverage_complete is False
    assert result.missing_ranges == ((date(2026, 6, 15), date(2026, 6, 30)),)


def test_ads_period_selection_uses_inclusive_chunk_dates(tmp_path: Path) -> None:
    sampling = tmp_path / "runtime" / "sampling"
    for index, (start, end) in enumerate(
        [("2026-06-01", "2026-06-14"), ("2026-06-15", "2026-06-28"), ("2026-06-29", "2026-06-30")],
        start=1,
    ):
        raw = tmp_path / f"ads-{index}.json"
        raw.write_text("[]", encoding="utf-8")
        _write_json(
            sampling / "ads_report_requests" / f"ads-{index}.json",
            {
                "ads_report_id": f"ads-{index}",
                "profile_id": "3917953989967300",
                "report_type_id": "spCampaigns",
                "data_start_date": start,
                "data_end_date": end,
                "processing_status": "COMPLETED",
                "download_status": "DOWNLOADED",
                "raw_file_path": str(raw),
            },
        )

    result = select_ads_period_raw_files(
        sampling_root=sampling,
        profile_id="3917953989967300",
        report_type_id="spCampaigns",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert result.coverage_complete is True
    assert result.selected_file_count == 3
