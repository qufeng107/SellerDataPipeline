from __future__ import annotations

from seller_data_pipeline.services.collect_ready_reports_service import CollectReadyReportsService


def run(*, limit: int) -> None:
    CollectReadyReportsService().run(limit=limit)
