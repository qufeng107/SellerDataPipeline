from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ReportRequestResult:
    report_id: str


class AmazonSpApiClient:
    """Placeholder SP-API client.

    Implement LWA auth, createReport, getReport, getReportDocument, and report download here.
    Keep this class focused on HTTP/API details only; business orchestration belongs in services.
    """

    def create_report(
        self,
        *,
        report_type: str,
        marketplace_ids: list[str],
        data_start_time: datetime | None = None,
        data_end_time: datetime | None = None,
    ) -> ReportRequestResult:
        logger.info(
            "create_report placeholder: report_type=%s marketplace_ids=%s start=%s end=%s",
            report_type,
            marketplace_ids,
            data_start_time,
            data_end_time,
        )
        raise NotImplementedError("Amazon SP-API create_report is not implemented yet")
