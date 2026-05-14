from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.local_manifest_store import utc_now_iso

ADS_TERMINAL_NO_DOWNLOAD_STATUSES = {"FAILED", "CANCELLED"}
ADS_DOWNLOADED_STATUSES = {"DOWNLOADED"}


class AdsManifestStore:
    """File-based manifest store for Amazon Ads local sampling mode."""

    def __init__(self, *, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.ads_profiles_path = self.root_dir / "ads_profiles.json"
        self.report_requests_dir = self.root_dir / "ads_report_requests"
        self.raw_files_dir = self.root_dir / "ads_raw_files"
        self.report_requests_dir.mkdir(parents=True, exist_ok=True)
        self.raw_files_dir.mkdir(parents=True, exist_ok=True)

    def save_profiles(self, profiles: list[dict[str, Any]]) -> Path:
        payload = {
            "schema_version": "local-ads-profiles-v1",
            "profiles": profiles,
            "updated_at_utc": utc_now_iso(),
        }
        return self._write_json(self.ads_profiles_path, payload)

    def read_profiles(self) -> list[dict[str, Any]]:
        if not self.ads_profiles_path.exists():
            return []
        payload = self._read_json(self.ads_profiles_path)
        profiles = payload.get("profiles")
        if not isinstance(profiles, list):
            return []
        return [item for item in profiles if isinstance(item, dict)]

    def save_report_request(self, manifest: dict[str, Any]) -> Path:
        report_id = str(manifest["ads_report_id"])
        manifest.setdefault("schema_version", "local-ads-report-request-v1")
        manifest.setdefault("created_at_utc", utc_now_iso())
        manifest["updated_at_utc"] = utc_now_iso()
        return self._write_json(self.report_request_path(report_id), manifest)

    def update_report_request(self, report_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        manifest = self.read_report_request(report_id)
        manifest.update(updates)
        manifest["updated_at_utc"] = utc_now_iso()
        self._write_json(self.report_request_path(report_id), manifest)
        return manifest

    def read_report_request(self, report_id: str) -> dict[str, Any]:
        path = self.report_request_path(report_id)
        if not path.exists():
            raise FileNotFoundError(f"Local Ads report request manifest not found: {path}")
        return self._read_json(path)

    def iter_report_requests(self) -> Iterable[dict[str, Any]]:
        for path in sorted(self.report_requests_dir.glob("*.json")):
            yield self._read_json(path)

    def iter_collectable_report_requests(self, *, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        collectable: list[dict[str, Any]] = []
        for manifest in self.iter_report_requests():
            status = str(manifest.get("processing_status", "")).upper()
            download_status = str(manifest.get("download_status", "")).upper()
            if download_status in ADS_DOWNLOADED_STATUSES:
                continue
            if status in ADS_TERMINAL_NO_DOWNLOAD_STATUSES:
                continue
            collectable.append(manifest)
            if len(collectable) >= limit:
                break
        return collectable

    def save_raw_file_manifest(self, *, report_id: str, manifest: dict[str, Any]) -> Path:
        manifest.setdefault("schema_version", "local-ads-raw-file-v1")
        manifest.setdefault("created_at_utc", utc_now_iso())
        manifest["updated_at_utc"] = utc_now_iso()
        return self._write_json(self.raw_file_manifest_path(report_id), manifest)

    def report_request_path(self, report_id: str) -> Path:
        return self.report_requests_dir / f"{self._safe_filename(report_id)}.json"

    def raw_file_manifest_path(self, report_id: str) -> Path:
        return self.raw_files_dir / f"{self._safe_filename(report_id)}.json"

    @staticmethod
    def _safe_filename(value: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
        if not isinstance(payload, dict):
            raise ValueError(f"Manifest JSON must be an object: {path}")
        return payload

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, ensure_ascii=False, indent=2, sort_keys=True)
            file_obj.write("\n")
        tmp_path.replace(path)
        return path
