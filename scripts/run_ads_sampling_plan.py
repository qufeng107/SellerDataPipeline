from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.sampling.ads_manifest_store import AdsManifestStore
from seller_data_pipeline.sampling.ads_report_sampling_plan import (
    AdsReportSamplingPlanItem,
    get_ads_sampling_plan,
)
from seller_data_pipeline.services.submit_ads_report_requests_service import (
    SubmitAdsReportRequestsService,
)

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit a curated Amazon Ads Reporting v3 sampling plan."
    )
    parser.add_argument(
        "--profile-id",
        help="Amazon Ads profile ID. Defaults to AMAZON_ADS_PROFILE_ID.",
    )
    parser.add_argument(
        "--only-report-type-id",
        action="append",
        default=[],
        help="Run only the specified Ads reportTypeId. Can be passed multiple times.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum plan items to process.")
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Override each plan item's lookback window. Useful for a small canary run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without calling Ads API.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Submit even if a matching manifest exists.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=2.0,
        help="Delay between Amazon Ads calls to reduce throttling risk. Default: 2.0.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    items = get_ads_sampling_plan()
    if args.only_report_type_id:
        allowed = set(args.only_report_type_id)
        items = [item for item in items if item.report_type_id in allowed]
    if args.limit is not None:
        items = items[: args.limit]

    store = AdsManifestStore(root_dir=settings.local_sampling_root)
    submit_service = SubmitAdsReportRequestsService(settings=settings, manifest_store=store)

    created: list[Path] = []
    skipped: list[AdsReportSamplingPlanItem] = []
    failed: list[tuple[AdsReportSamplingPlanItem, str]] = []

    print(f"Amazon Ads sampling plan items: {len(items)}")
    for index, item in enumerate(items, start=1):
        effective_days = args.days or item.days
        print(_format_plan_line(index=index, item=item, effective_days=effective_days))
        if args.dry_run:
            continue
        profile_id = args.profile_id or settings.amazon_ads_profile_id
        if not args.force and profile_id and _has_matching_manifest(
            store=store,
            item=item,
            profile_id=profile_id,
        ):
            logger.info(
                "Skipping existing Amazon Ads sample: report_type_id=%s",
                item.report_type_id,
            )
            skipped.append(item)
            continue
        try:
            created.append(
                submit_service.run(
                    profile_id=args.profile_id,
                    report_type_id=item.report_type_id,
                    ad_product=item.ad_product,
                    group_by=list(item.group_by),
                    columns=list(item.columns),
                    days=effective_days,
                    time_unit=item.time_unit,
                )
            )
        except Exception as exc:  # noqa: BLE001 - keep batch sampling resilient.
            logger.exception(
                "Amazon Ads sampling item failed: report_type_id=%s",
                item.report_type_id,
            )
            failed.append((item, str(exc)))
        if args.pause_seconds > 0 and index < len(items):
            time.sleep(args.pause_seconds)

    if args.dry_run:
        return

    print(f"Created manifest(s): {len(created)}")
    for path in created:
        print(f"Manifest: {path}")
    print(f"Skipped existing item(s): {len(skipped)}")
    print(f"Failed item(s): {len(failed)}")
    for item, message in failed:
        print(f"FAILED {item.report_type_id}: {message}")


def _format_plan_line(
    *,
    index: int,
    item: AdsReportSamplingPlanItem,
    effective_days: int | None = None,
) -> str:
    days = effective_days if effective_days is not None else item.days
    details = [
        f"{index}.",
        item.ad_product,
        item.report_type_id,
        f"days={days}",
        f"timeUnit={item.time_unit}",
        f"groupBy={list(item.group_by)}",
        f"columns={len(item.columns)}",
        "-",
        item.label,
    ]
    return " ".join(details)


def _has_matching_manifest(
    *,
    store: AdsManifestStore,
    item: AdsReportSamplingPlanItem,
    profile_id: str,
) -> bool:
    for manifest in store.iter_report_requests():
        if manifest.get("profile_id") != profile_id:
            continue
        if manifest.get("report_type_id") != item.report_type_id:
            continue
        if manifest.get("ad_product") != item.ad_product:
            continue
        if list(manifest.get("group_by") or []) != list(item.group_by):
            continue
        if str(manifest.get("time_unit") or "") != item.time_unit:
            continue
        if manifest.get("download_status") == "DOWNLOADED":
            return True
        if manifest.get("processing_status") in {"PENDING", "PROCESSING", "COMPLETED", "SUBMITTED"}:
            return True
    return False


if __name__ == "__main__":
    main()
