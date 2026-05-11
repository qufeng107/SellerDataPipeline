from __future__ import annotations

from seller_data_pipeline.services.generate_periodic_reports_service import GeneratePeriodicReportsService


def run(*, report_type: str) -> None:
    GeneratePeriodicReportsService().run(report_type=report_type)
