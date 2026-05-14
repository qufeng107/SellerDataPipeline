from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TERMINAL_NO_DOWNLOAD_STATUSES = {"CANCELLED"}
DOWNLOADED_STATUSES = {"DOWNLOADED", "DIAGNOSTIC_DOWNLOADED"}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class LocalManifestStore:
    """File-based report request/raw-file manifest store for local sampling mode."""

    def __init__(self, *, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.report_requests_dir = self.root_dir / "report_requests"
        self.raw_files_dir = self.root_dir / "raw_files"
        self.report_requests_dir.mkdir(parents=True, exist_ok=True)
        self.raw_files_dir.mkdir(parents=True, exist_ok=True)

    def save_report_request(self, manifest: dict[str, Any]) -> Path:
        report_id = str(manifest["report_id"])
        manifest.setdefault("schema_version", "local-report-request-v1")
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
            raise FileNotFoundError(f"Local report request manifest not found: {path}")
        return self._read_json(path)

    def iter_report_requests(self) -> Iterable[dict[str, Any]]:
        for path in sorted(self.report_requests_dir.glob("*.json")):
            yield self._read_json(path)

    def iter_collectable_report_requests(self, *, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        collectable: list[dict[str, Any]] = []
        for manifest in self.iter_report_requests():
            processing_status = str(manifest.get("processing_status", "")).upper()
            download_status = str(manifest.get("download_status", "")).upper()
            if download_status in DOWNLOADED_STATUSES:
                continue
            if processing_status in TERMINAL_NO_DOWNLOAD_STATUSES:
                continue
            if processing_status == "FATAL" and not manifest.get("report_document_id"):
                continue
            collectable.append(manifest)
            if len(collectable) >= limit:
                break
        return collectable

    def save_raw_file_manifest(self, *, report_id: str, manifest: dict[str, Any]) -> Path:
        manifest.setdefault("schema_version", "local-raw-file-v1")
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
