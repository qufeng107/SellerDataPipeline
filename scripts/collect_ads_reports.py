from __future__ import annotations

import argparse

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.services.collect_ads_reports_service import CollectAdsReportsService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect ready Amazon Ads reports in local sampling mode."
    )
    parser.add_argument("--limit", type=int, default=20, help="Max pending reports to check.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    results = CollectAdsReportsService(settings=settings).run(limit=args.limit)
    print(f"Checked {len(results)} Amazon Ads report request(s).")
    for result in results:
        print(
            "ads_report_id={ads_report_id} processing_status={processing_status} "
            "download_status={download_status} raw_file_path={raw_file_path}".format(
                ads_report_id=result.get("ads_report_id"),
                processing_status=result.get("processing_status"),
                download_status=result.get("download_status"),
                raw_file_path=result.get("raw_file_path"),
            )
        )


if __name__ == "__main__":
    main()
