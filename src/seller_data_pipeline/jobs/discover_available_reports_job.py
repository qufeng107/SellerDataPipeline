from __future__ import annotations

from pathlib import Path

from seller_data_pipeline.integrations.amazon.report_types import SETTLEMENT_V2
from seller_data_pipeline.services.discover_available_reports_service import (
    SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS,
    DiscoverAvailableReportsService,
)


def run(
    *,
    report_type: str = SETTLEMENT_V2,
    marketplace_ids: list[str] | None = None,
    days: int | None = SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS,
    page_size: int = 20,
    max_pages: int = 3,
) -> list[Path]:
    return DiscoverAvailableReportsService().run(
        report_type=report_type,
        marketplace_ids=marketplace_ids,
        days=days,
        page_size=page_size,
        max_pages=max_pages,
    )
