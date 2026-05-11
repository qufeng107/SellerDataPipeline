from __future__ import annotations

import logging
from datetime import date

from seller_data_pipeline.common.date_windows import recent_days_window

logger = logging.getLogger(__name__)


class SubmitReportRequestsService:
    """Submit Amazon report requests and persist report IDs."""

    def run(self, *, days: int, today: date | None = None) -> None:
        today = today or date.today()
        window = recent_days_window(today=today, days=days)
        logger.info(
            "submit report requests placeholder: start=%s end=%s days=%s",
            window.start,
            window.end,
            days,
        )
        # TODO: call AmazonSpApiClient.create_report and insert amazon_report_request rows.
