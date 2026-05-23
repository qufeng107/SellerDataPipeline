from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from seller_data_pipeline.common.date_windows import (
    DateWindow,
    chunk_inclusive_date_range,
)
from seller_data_pipeline.config.settings import Settings, get_settings
from seller_data_pipeline.sampling.ads_manifest_store import AdsManifestStore
from seller_data_pipeline.sampling.ads_report_sampling_plan import (
    AdsReportSamplingPlanItem,
    get_ads_sampling_plan,
)
from seller_data_pipeline.sampling.local_manifest_store import LocalManifestStore
from seller_data_pipeline.services.submit_ads_report_requests_service import (
    SubmitAdsReportRequestsService,
)
from seller_data_pipeline.services.submit_report_requests_service import SubmitReportRequestsService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillWindowResult:
    source_system: str
    report_type: str
    start_date: date
    end_date: date
    status: str
    manifest_path: Path | None = None
    message: str = ""


@dataclass(frozen=True)
class BackfillRunResult:
    source_system: str
    created_count: int
    skipped_count: int
    failed_count: int
    dry_run: bool
    window_results: tuple[BackfillWindowResult, ...]

    @property
    def total_count(self) -> int:
        return len(self.window_results)


def build_backfill_windows(
    *,
    start_date: date,
    end_date: date,
    chunk_days: int,
) -> tuple[DateWindow, ...]:
    return chunk_inclusive_date_range(start=start_date, end=end_date, chunk_days=chunk_days)


class BackfillReportRequestsService:
    """Submit SP-API report requests for explicit historical date windows."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        manifest_store: LocalManifestStore | None = None,
        submit_service: SubmitReportRequestsService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.manifest_store = manifest_store or LocalManifestStore(
            root_dir=self.settings.local_sampling_root
        )
        self.submit_service = submit_service or SubmitReportRequestsService(
            settings=self.settings,
            manifest_store=self.manifest_store,
        )

    def run(
        self,
        *,
        report_type: str,
        marketplace_ids: list[str] | None,
        start_date: date,
        end_date: date,
        chunk_days: int,
        report_options: dict[str, str] | None = None,
        dry_run: bool = True,
        force: bool = False,
        pause_seconds: float = 2.0,
    ) -> BackfillRunResult:
        windows = build_backfill_windows(
            start_date=start_date,
            end_date=end_date,
            chunk_days=chunk_days,
        )
        normalized_marketplace_ids = marketplace_ids or self._default_marketplace_ids()
        results: list[BackfillWindowResult] = []
        for index, window in enumerate(windows, start=1):
            if not force and self._has_matching_manifest(
                report_type=report_type,
                marketplace_ids=normalized_marketplace_ids,
                window=window,
                report_options=report_options,
            ):
                results.append(
                    BackfillWindowResult(
                        source_system="sp_api_reports",
                        report_type=report_type,
                        start_date=window.start,
                        end_date=window.end,
                        status="skipped_existing",
                        message="Matching local manifest already exists.",
                    )
                )
                continue
            if dry_run:
                results.append(
                    BackfillWindowResult(
                        source_system="sp_api_reports",
                        report_type=report_type,
                        start_date=window.start,
                        end_date=window.end,
                        status="dry_run_planned",
                    )
                )
                continue
            try:
                manifest_path = self.submit_service.run(
                    report_type=report_type,
                    marketplace_ids=normalized_marketplace_ids,
                    days=None,
                    start_date=window.start,
                    end_date=window.end,
                    report_options=report_options,
                )
                results.append(
                    BackfillWindowResult(
                        source_system="sp_api_reports",
                        report_type=report_type,
                        start_date=window.start,
                        end_date=window.end,
                        status="created",
                        manifest_path=manifest_path,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - keep historical batches resilient.
                logger.exception(
                    "SP-API backfill window failed: report_type=%s start=%s end=%s",
                    report_type,
                    window.start,
                    window.end,
                )
                results.append(
                    BackfillWindowResult(
                        source_system="sp_api_reports",
                        report_type=report_type,
                        start_date=window.start,
                        end_date=window.end,
                        status="failed",
                        message=str(exc),
                    )
                )
            if pause_seconds > 0 and index < len(windows):
                time.sleep(pause_seconds)

        return _build_run_result(source_system="sp_api_reports", dry_run=dry_run, results=results)

    def _default_marketplace_ids(self) -> list[str]:
        if not self.settings.amazon_marketplace_id:
            raise ValueError("AMAZON_MARKETPLACE_ID is required or pass --marketplace-id")
        return [self.settings.amazon_marketplace_id]

    def _has_matching_manifest(
        self,
        *,
        report_type: str,
        marketplace_ids: list[str],
        window: DateWindow,
        report_options: dict[str, str] | None,
    ) -> bool:
        expected_start = f"{window.start.isoformat()}T00:00:00Z"
        # SP-API dataEndTime is written as the exclusive next-day midnight for inclusive CLI ranges.
        expected_end = f"{_next_day(window.end).isoformat()}T00:00:00Z"
        expected_options_keys = set(report_options or {})
        for manifest in self.manifest_store.iter_report_requests():
            if manifest.get("report_type") != report_type:
                continue
            if [str(value) for value in manifest.get("marketplace_ids", [])] != marketplace_ids:
                continue
            if manifest.get("data_start_time") != expected_start:
                continue
            if manifest.get("data_end_time") != expected_end:
                continue
            actual_options = dict(manifest.get("report_options") or {})
            if expected_options_keys and not set(actual_options).issuperset(expected_options_keys):
                continue
            if not _manifest_is_active_or_downloaded(manifest):
                continue
            return True
        return False


class BackfillAdsReportsService:
    """Submit Amazon Ads Reporting v3 requests for explicit historical date windows."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        manifest_store: AdsManifestStore | None = None,
        submit_service: SubmitAdsReportRequestsService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.manifest_store = manifest_store or AdsManifestStore(
            root_dir=self.settings.local_sampling_root
        )
        self.submit_service = submit_service or SubmitAdsReportRequestsService(
            settings=self.settings,
            manifest_store=self.manifest_store,
        )

    def run(
        self,
        *,
        profile_id: str | None,
        start_date: date,
        end_date: date,
        chunk_days: int,
        only_report_type_ids: list[str] | None = None,
        dry_run: bool = True,
        force: bool = False,
        pause_seconds: float = 2.0,
    ) -> BackfillRunResult:
        resolved_profile_id = profile_id or self.settings.amazon_ads_profile_id
        if not resolved_profile_id:
            raise ValueError("AMAZON_ADS_PROFILE_ID is required or pass --profile-id")
        windows = build_backfill_windows(
            start_date=start_date,
            end_date=end_date,
            chunk_days=chunk_days,
        )
        items = _select_ads_plan_items(only_report_type_ids=only_report_type_ids)
        planned_pairs = [(window, item) for window in windows for item in items]
        results: list[BackfillWindowResult] = []
        for index, (window, item) in enumerate(planned_pairs, start=1):
            if not force and self._has_matching_manifest(
                profile_id=resolved_profile_id,
                window=window,
                item=item,
            ):
                results.append(
                    BackfillWindowResult(
                        source_system="amazon_ads",
                        report_type=item.report_type_id,
                        start_date=window.start,
                        end_date=window.end,
                        status="skipped_existing",
                        message="Matching local Ads manifest already exists.",
                    )
                )
                continue
            if dry_run:
                results.append(
                    BackfillWindowResult(
                        source_system="amazon_ads",
                        report_type=item.report_type_id,
                        start_date=window.start,
                        end_date=window.end,
                        status="dry_run_planned",
                    )
                )
                continue
            try:
                manifest_path = self.submit_service.run(
                    profile_id=resolved_profile_id,
                    report_type_id=item.report_type_id,
                    ad_product=item.ad_product,
                    group_by=list(item.group_by),
                    columns=list(item.columns),
                    days=None,
                    start_date=window.start,
                    end_date=window.end,
                    time_unit=item.time_unit,
                )
                results.append(
                    BackfillWindowResult(
                        source_system="amazon_ads",
                        report_type=item.report_type_id,
                        start_date=window.start,
                        end_date=window.end,
                        status="created",
                        manifest_path=manifest_path,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - keep historical batches resilient.
                logger.exception(
                    "Ads backfill window failed: report_type_id=%s start=%s end=%s",
                    item.report_type_id,
                    window.start,
                    window.end,
                )
                results.append(
                    BackfillWindowResult(
                        source_system="amazon_ads",
                        report_type=item.report_type_id,
                        start_date=window.start,
                        end_date=window.end,
                        status="failed",
                        message=str(exc),
                    )
                )
            if pause_seconds > 0 and index < len(planned_pairs):
                time.sleep(pause_seconds)

        return _build_run_result(source_system="amazon_ads", dry_run=dry_run, results=results)

    def _has_matching_manifest(
        self,
        *,
        profile_id: str,
        window: DateWindow,
        item: AdsReportSamplingPlanItem,
    ) -> bool:
        for manifest in self.manifest_store.iter_report_requests():
            if str(manifest.get("profile_id") or "") != profile_id:
                continue
            if manifest.get("report_type_id") != item.report_type_id:
                continue
            if manifest.get("ad_product") != item.ad_product:
                continue
            if list(manifest.get("group_by") or []) != list(item.group_by):
                continue
            if str(manifest.get("time_unit") or "") != item.time_unit:
                continue
            if manifest.get("data_start_date") != window.start.isoformat():
                continue
            if manifest.get("data_end_date") != window.end.isoformat():
                continue
            if not _manifest_is_active_or_downloaded(manifest):
                continue
            return True
        return False


def _select_ads_plan_items(
    *,
    only_report_type_ids: list[str] | None,
) -> list[AdsReportSamplingPlanItem]:
    items = get_ads_sampling_plan()
    if only_report_type_ids:
        allowed = set(only_report_type_ids)
        items = [item for item in items if item.report_type_id in allowed]
    if not items:
        raise ValueError("No Amazon Ads report types matched the requested filter")
    return items


def _manifest_is_active_or_downloaded(manifest: dict[str, Any]) -> bool:
    download_status = str(manifest.get("download_status") or "").upper()
    processing_status = str(manifest.get("processing_status") or "").upper()
    if download_status in {"DOWNLOADED", "DIAGNOSTIC_DOWNLOADED"}:
        return True
    return processing_status in {
        "SUBMITTED",
        "IN_QUEUE",
        "IN_PROGRESS",
        "DONE",
        "PENDING",
        "PROCESSING",
        "COMPLETED",
    }


def _build_run_result(
    *,
    source_system: str,
    dry_run: bool,
    results: list[BackfillWindowResult],
) -> BackfillRunResult:
    return BackfillRunResult(
        source_system=source_system,
        dry_run=dry_run,
        created_count=sum(1 for row in results if row.status == "created"),
        skipped_count=sum(1 for row in results if row.status == "skipped_existing"),
        failed_count=sum(1 for row in results if row.status == "failed"),
        window_results=tuple(results),
    )


def _next_day(value: date) -> date:
    return date.fromordinal(value.toordinal() + 1)
