from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.sampling.local_manifest_store import LocalManifestStore
from seller_data_pipeline.sampling.report_sampling_plan import (
    ReportSamplingPlanItem,
    get_sampling_plan,
)
from seller_data_pipeline.services.discover_available_reports_service import (
    DiscoverAvailableReportsService,
)
from seller_data_pipeline.services.submit_report_requests_service import SubmitReportRequestsService

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit/discover a curated Amazon report sampling plan."
    )
    parser.add_argument(
        "--marketplace-id",
        action="append",
        dest="marketplace_ids",
        help=(
            "Amazon marketplace ID. Can be passed multiple times. "
            "Defaults to AMAZON_MARKETPLACE_ID."
        ),
    )
    parser.add_argument(
        "--include-sensitive",
        action="store_true",
        help="Include reports that may contain buyer/customer-identifying fields or comments.",
    )
    parser.add_argument(
        "--only-report-type",
        action="append",
        default=[],
        help="Run only the specified report type. Can be passed multiple times.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of plan items to process after filtering.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without calling Amazon SP-API.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Submit even when a matching local manifest already exists.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=2.0,
        help="Delay between Amazon calls to reduce throttling risk. Default: 2.0.",
    )
    parser.add_argument(
        "--discovery-page-size",
        type=int,
        default=20,
        help="Page size for getReports discovery items. Default: 20.",
    )
    parser.add_argument(
        "--discovery-max-pages",
        type=int,
        default=3,
        help="Max getReports pages for discovery items. Default: 3.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    items = get_sampling_plan(include_sensitive=args.include_sensitive)
    if args.only_report_type:
        allowed = set(args.only_report_type)
        items = [item for item in items if item.report_type in allowed]
    if args.limit is not None:
        items = items[: args.limit]

    store = LocalManifestStore(root_dir=settings.local_sampling_root)
    submit_service = SubmitReportRequestsService(settings=settings, manifest_store=store)
    discover_service = DiscoverAvailableReportsService(settings=settings, manifest_store=store)

    created_or_discovered: list[Path] = []
    skipped: list[ReportSamplingPlanItem] = []
    failed: list[tuple[ReportSamplingPlanItem, str]] = []

    print(f"Sampling plan items: {len(items)}")
    for index, item in enumerate(items, start=1):
        print(_format_plan_line(index=index, item=item))
        if args.dry_run:
            continue

        if (
            not args.force
            and item.mode == "request"
            and _has_matching_manifest(
                store=store,
                item=item,
                marketplace_ids=args.marketplace_ids,
            )
        ):
            logger.info("Skipping existing report sample: report_type=%s", item.report_type)
            skipped.append(item)
            continue

        try:
            if item.mode == "request":
                created_or_discovered.append(
                    submit_service.run(
                        report_type=item.report_type,
                        marketplace_ids=args.marketplace_ids,
                        days=item.days,
                        report_options=item.report_options or None,
                    )
                )
            elif item.mode == "discover":
                created_or_discovered.extend(
                    discover_service.run(
                        report_type=item.report_type,
                        marketplace_ids=args.marketplace_ids,
                        days=item.days,
                        page_size=args.discovery_page_size,
                        max_pages=args.discovery_max_pages,
                    )
                )
            else:
                raise ValueError(f"Unsupported sampling mode: {item.mode}")
        except Exception as exc:  # noqa: BLE001 - keep batch sampling resilient.
            logger.exception("Sampling plan item failed: report_type=%s", item.report_type)
            failed.append((item, str(exc)))

        if args.pause_seconds > 0 and index < len(items):
            time.sleep(args.pause_seconds)

    if args.dry_run:
        return

    print(f"Created/discovered manifest(s): {len(created_or_discovered)}")
    for path in created_or_discovered:
        print(f"Manifest: {path}")
    print(f"Skipped existing request item(s): {len(skipped)}")
    print(f"Failed item(s): {len(failed)}")
    for item, message in failed:
        print(f"FAILED {item.report_type}: {message}")


def _format_plan_line(*, index: int, item: ReportSamplingPlanItem) -> str:
    details = [f"{index}.", item.mode.upper(), item.report_type]
    if item.days is not None:
        details.append(f"days={item.days}")
    if item.report_options:
        details.append(f"options={item.report_options}")
    if item.sensitive:
        details.append("sensitive=true")
    details.append(f"- {item.label}")
    return " ".join(details)


def _has_matching_manifest(
    *,
    store: LocalManifestStore,
    item: ReportSamplingPlanItem,
    marketplace_ids: list[str] | None,
) -> bool:
    expected_marketplaces = marketplace_ids
    for manifest in store.iter_report_requests():
        if manifest.get("report_type") != item.report_type:
            continue
        if not _report_options_match(
            expected_template=item.report_options,
            actual=dict(manifest.get("report_options") or {}),
        ):
            continue
        if expected_marketplaces is not None:
            manifest_marketplaces = [str(value) for value in manifest.get("marketplace_ids", [])]
            if manifest_marketplaces != expected_marketplaces:
                continue
        if manifest.get("download_status") in {"DOWNLOADED", "DIAGNOSTIC_DOWNLOADED"}:
            return True
        if manifest.get("processing_status") in {
            "SUBMITTED",
            "IN_QUEUE",
            "IN_PROGRESS",
            "DONE",
            "CANCELLED",
            "FATAL",
        }:
            return True
    return False


def _report_options_match(
    *,
    expected_template: dict[str, str],
    actual: dict[str, str],
) -> bool:
    if set(actual) != set(expected_template):
        return False

    for key, expected_value in expected_template.items():
        actual_value = str(actual.get(key) or "")
        if expected_value in {"{data_start_time}", "{data_end_time}"}:
            if not actual_value:
                return False
            continue
        if actual_value != expected_value:
            return False
    return True


if __name__ == "__main__":
    main()
