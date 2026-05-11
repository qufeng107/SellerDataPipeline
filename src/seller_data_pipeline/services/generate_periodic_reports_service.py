from __future__ import annotations

import logging
from datetime import date

from seller_data_pipeline.common.date_windows import previous_complete_week, stable_profit_week

logger = logging.getLogger(__name__)


class GeneratePeriodicReportsService:
    """Generate weekly, monthly, or quarterly Excel reports."""

    def run(self, *, report_type: str, today: date | None = None) -> None:
        today = today or date.today()
        if report_type == "weekly":
            quick = previous_complete_week(today)
            stable = stable_profit_week(today)
            logger.info(
                "generate weekly report placeholder: quick=%s..%s stable=%s..%s",
                quick.start,
                quick.end,
                stable.start,
                stable.end,
            )
        else:
            logger.info("generate %s report placeholder", report_type)
        # TODO: query DB, calculate snapshots, build Excel, upload to blob, send email.
