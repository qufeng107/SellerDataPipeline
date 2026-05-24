from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.common.exceptions import SellerDataPipelineError
from seller_data_pipeline.services.report_delivery_templates import (
    AUDIENCES,
    SUPPORTED_REPORT_TYPES,
    EmailDraft,
    get_template,
)

REPORT_DELIVERY_VERSION = "v1.0"
DEFAULT_DELIVERY_ROOT = "runtime/report_delivery"


class ReportDeliveryError(SellerDataPipelineError):
    """Raised when a report delivery pack cannot be generated."""


@dataclass(frozen=True)
class AttachmentSpec:
    kind: str
    source_path: str
    pack_path: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source_path": self.source_path,
            "pack_path": self.pack_path,
            "required": self.required,
        }


@dataclass(frozen=True)
class SendGuardResult:
    send_allowed: bool
    severity: str
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "send_allowed": self.send_allowed,
            "severity": self.severity,
            "messages": self.messages,
        }


@dataclass(frozen=True)
class ReportDeliveryPackResult:
    output_dir: Path
    manifest_path: Path
    subject_path: Path
    body_html_path: Path
    body_text_path: Path
    report_type: str
    audience: str
    status: str
    dry_run: bool
    email: EmailDraft
    send_guard: SendGuardResult
    attachments: list[AttachmentSpec]
    warnings: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "manifest_path": str(self.manifest_path),
            "subject_path": str(self.subject_path),
            "body_html_path": str(self.body_html_path),
            "body_text_path": str(self.body_text_path),
            "report_type": self.report_type,
            "audience": self.audience,
            "status": self.status,
            "dry_run": self.dry_run,
            "subject": self.email.subject,
            "send_guard": self.send_guard.to_dict(),
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "warnings": self.warnings,
        }


class ReportDeliveryPackService:
    """Create a local email draft pack from an existing report JSON + XLSX workbook."""

    def generate_pack(
        self,
        *,
        report_json_path: str | Path,
        template: str = "auto",
        audience: str = "internal",
        xlsx_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        output_root: str | Path = DEFAULT_DELIVERY_ROOT,
        include_json_attachment: bool = False,
        copy_attachments: bool = True,
        allow_partial: bool | None = None,
        allow_needs_review: bool = False,
        dry_run: bool = True,
    ) -> ReportDeliveryPackResult:
        report_json = Path(report_json_path)
        if not report_json.exists():
            raise ReportDeliveryError(f"report_json does not exist: {report_json}")
        report = _load_json(report_json)
        report_type = _resolve_report_type(report, template)
        if audience not in AUDIENCES:
            raise ReportDeliveryError(
                f"Unsupported audience: {audience}. Supported: {', '.join(sorted(AUDIENCES))}."
            )
        template_adapter = get_template(report_type)
        email = template_adapter.render(report, audience=audience)
        source_xlsx = _resolve_xlsx_path(report, report_json=report_json, override=xlsx_path)
        status = str(report.get("status") or "unknown")
        send_guard = _build_send_guard(
            status=status,
            audience=audience,
            allow_partial=_default_allow_partial(audience)
            if allow_partial is None
            else allow_partial,
            allow_needs_review=allow_needs_review,
        )
        target_dir = Path(output_dir) if output_dir else _default_output_dir(report, output_root)
        target_dir.mkdir(parents=True, exist_ok=True)
        attachments_dir = target_dir / "attachments"
        if copy_attachments:
            if attachments_dir.exists():
                shutil.rmtree(attachments_dir)
            attachments_dir.mkdir(parents=True, exist_ok=True)
        attachments: list[AttachmentSpec] = []
        attachments.append(
            _prepare_attachment(
                source_path=source_xlsx,
                output_dir=target_dir,
                attachments_dir=attachments_dir,
                kind="xlsx",
                copy_attachments=copy_attachments,
            )
        )
        if include_json_attachment:
            attachments.append(
                _prepare_attachment(
                    source_path=report_json,
                    output_dir=target_dir,
                    attachments_dir=attachments_dir,
                    kind="json",
                    copy_attachments=copy_attachments,
                )
            )
        subject_path = target_dir / "email_subject.txt"
        body_html_path = target_dir / "email_body.html"
        body_text_path = target_dir / "email_body.txt"
        manifest_path = target_dir / "delivery_manifest.json"
        subject_path.write_text(email.subject.strip() + "\n", encoding="utf-8")
        body_html_path.write_text(email.body_html, encoding="utf-8")
        body_text_path.write_text(email.body_text, encoding="utf-8")
        warnings = _extract_warnings(report)
        manifest = _build_manifest(
            report=report,
            report_json=report_json,
            source_xlsx=source_xlsx,
            email=email,
            audience=audience,
            target_dir=target_dir,
            subject_path=subject_path,
            body_html_path=body_html_path,
            body_text_path=body_text_path,
            attachments=attachments,
            send_guard=send_guard,
            warnings=warnings,
            dry_run=dry_run,
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return ReportDeliveryPackResult(
            output_dir=target_dir,
            manifest_path=manifest_path,
            subject_path=subject_path,
            body_html_path=body_html_path,
            body_text_path=body_text_path,
            report_type=report_type,
            audience=audience,
            status=status,
            dry_run=dry_run,
            email=email,
            send_guard=send_guard,
            attachments=attachments,
            warnings=warnings,
        )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReportDeliveryError(f"Invalid report JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReportDeliveryError(f"Report JSON root must be an object: {path}")
    return payload


def _resolve_report_type(report: dict[str, Any], template: str) -> str:
    report_type = str(report.get("report_type") or "").strip()
    if template != "auto":
        report_type = template
    if report_type not in SUPPORTED_REPORT_TYPES:
        supported = ", ".join(sorted(SUPPORTED_REPORT_TYPES))
        raise ReportDeliveryError(
            f"Unsupported report_type: {report_type}. Supported: {supported}."
        )
    return report_type


def _resolve_xlsx_path(
    report: dict[str, Any], *, report_json: Path, override: str | Path | None
) -> Path:
    candidates: list[Path] = []
    if override is not None:
        candidates.append(Path(override))
    else:
        output_files = report.get("output_files") or {}
        if not isinstance(output_files, dict) or not output_files.get("xlsx"):
            raise ReportDeliveryError("Report JSON is missing output_files.xlsx; pass --xlsx-path.")
        raw_xlsx = str(output_files["xlsx"])
        candidates.extend(_path_candidates(raw_xlsx, report_json=report_json))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    candidate_text = ", ".join(str(path) for path in candidates) or "<none>"
    raise ReportDeliveryError(f"XLSX attachment not found. Checked: {candidate_text}")


def _path_candidates(raw_path: str, *, report_json: Path) -> list[Path]:
    normalized = raw_path.replace("\\", "/")
    paths = [Path(raw_path), Path(normalized)]
    paths.append(report_json.parent / Path(normalized).name)
    paths.append(report_json.with_suffix(".xlsx"))
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def _default_output_dir(report: dict[str, Any], output_root: str | Path) -> Path:
    report_type = str(report.get("report_type") or "unknown_report")
    marketplace_id = str(report.get("marketplace_id") or "").strip()
    profile_id = str(report.get("profile_id") or "").strip()
    if marketplace_id and profile_id:
        scope_id = f"{marketplace_id}_{profile_id}"
    elif marketplace_id:
        scope_id = marketplace_id
    elif profile_id:
        scope_id = profile_id
    else:
        scope_id = "unknown_scope"
    return Path(output_root) / report_type / scope_id / _period_key(report)


def _period_key(report: dict[str, Any]) -> str:
    period = report.get("period") or {}
    if not isinstance(period, dict):
        return "unknown_period"
    if period.get("month"):
        return str(period["month"])
    if period.get("week_start") and period.get("week_end"):
        return f"{period['week_start']}_{period['week_end']}"
    if period.get("start_date") and period.get("end_date"):
        return f"{period['start_date']}_{period['end_date']}"
    return "unknown_period"


def _default_allow_partial(audience: str) -> bool:
    return audience in {"internal", "operations", "ads_operator"}


def _build_send_guard(
    *,
    status: str,
    audience: str,
    allow_partial: bool,
    allow_needs_review: bool,
) -> SendGuardResult:
    normalized_status = status.lower()
    messages: list[str] = []
    if normalized_status in {"no_data", "no_ads_data"}:
        messages.append(f"Report status is {status}; do not send as a normal report.")
    if normalized_status == "needs_review" and not allow_needs_review:
        messages.append("Report status is needs_review; resolve issues or pass override later.")
    if normalized_status == "partial" and not allow_partial:
        messages.append(
            f"Audience {audience} is not allowed to receive partial reports by default."
        )
    if audience in {"shareholders", "accountant"} and normalized_status in {
        "partial",
        "needs_review",
    }:
        if normalized_status == "partial" and allow_partial:
            messages.append(
                f"Audience {audience} is sensitive; partial reports should be reviewed manually."
            )
    if messages:
        return SendGuardResult(send_allowed=False, severity="blocked", messages=messages)
    return SendGuardResult(send_allowed=True, severity="ok", messages=[])


def _prepare_attachment(
    *,
    source_path: Path,
    output_dir: Path,
    attachments_dir: Path,
    kind: str,
    copy_attachments: bool,
) -> AttachmentSpec:
    if not source_path.exists():
        raise ReportDeliveryError(f"Attachment source does not exist: {source_path}")
    if copy_attachments:
        target_path = attachments_dir / source_path.name
        if source_path.resolve() != target_path.resolve():
            shutil.copy2(source_path, target_path)
        pack_path = target_path.relative_to(output_dir)
    else:
        pack_path = source_path
    return AttachmentSpec(
        kind=kind,
        source_path=str(source_path),
        pack_path=str(pack_path),
        required=True,
    )


def _extract_warnings(report: dict[str, Any]) -> list[dict[str, Any]]:
    warnings = report.get("warnings")
    if not isinstance(warnings, list):
        return []
    return [item for item in warnings if isinstance(item, dict)]


def _build_manifest(
    *,
    report: dict[str, Any],
    report_json: Path,
    source_xlsx: Path,
    email: EmailDraft,
    audience: str,
    target_dir: Path,
    subject_path: Path,
    body_html_path: Path,
    body_text_path: Path,
    attachments: list[AttachmentSpec],
    send_guard: SendGuardResult,
    warnings: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    period = report.get("period") if isinstance(report.get("period"), dict) else {}
    return {
        "delivery_type": "report_email_pack",
        "version": REPORT_DELIVERY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "report": {
            "report_type": report.get("report_type"),
            "report_version": report.get("version"),
            "status": report.get("status"),
            "marketplace_id": report.get("marketplace_id"),
            "profile_id": report.get("profile_id"),
            "period": period,
            "period_key": _period_key(report),
            "source_json_path": str(report_json),
            "source_xlsx_path": str(source_xlsx),
        },
        "email": {
            "template": email.template,
            "audience": audience,
            "subject": email.subject,
            "subject_path": str(subject_path.relative_to(target_dir)),
            "body_html_path": str(body_html_path.relative_to(target_dir)),
            "body_text_path": str(body_text_path.relative_to(target_dir)),
        },
        "attachments": [attachment.to_dict() for attachment in attachments],
        "send_guard": send_guard.to_dict(),
        "warnings": warnings,
    }
