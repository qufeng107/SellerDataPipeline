from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReportRequestRecord:
    marketplace: str
    report_type: str
    data_start_time: datetime | None
    data_end_time: datetime | None
    report_id: str | None
    processing_status: str


class ReportRequestRepository:
    """Repository placeholder for amazon_report_request table."""

    def insert_submitted_request(self, record: ReportRequestRecord) -> None:
        raise NotImplementedError

    def list_pending_requests(self, limit: int = 20) -> list[ReportRequestRecord]:
        raise NotImplementedError
