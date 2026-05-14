from __future__ import annotations

from pathlib import Path

from seller_data_pipeline.integrations.amazon.report_types import LISTINGS_ALL_DATA
from seller_data_pipeline.services.submit_report_requests_service import SubmitReportRequestsService


def run(
    *,
    report_type: str = LISTINGS_ALL_DATA,
    marketplace_ids: list[str] | None = None,
    days: int | None = None,
    report_options: dict[str, str] | None = None,
) -> Path:
    return SubmitReportRequestsService().run(
        report_type=report_type,
        marketplace_ids=marketplace_ids,
        days=days,
        report_options=report_options,
    )
