from __future__ import annotations

from seller_data_pipeline.services.submit_report_requests_service import SubmitReportRequestsService


def run(*, days: int) -> None:
    SubmitReportRequestsService().run(days=days)
