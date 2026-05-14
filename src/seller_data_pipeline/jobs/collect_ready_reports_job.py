from __future__ import annotations

from typing import Any

from seller_data_pipeline.services.collect_ready_reports_service import CollectReadyReportsService


def run(*, limit: int) -> list[dict[str, Any]]:
    return CollectReadyReportsService().run(limit=limit)
