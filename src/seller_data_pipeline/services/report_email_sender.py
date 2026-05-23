from __future__ import annotations

import json
import mimetypes
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from time import sleep
from typing import Any, Callable

from seller_data_pipeline.common.exceptions import SellerDataPipelineError
from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.report_email_recipient_repo import (
    ReportEmailRecipientRecord,
    ReportEmailRecipientRepo,
)

DEFAULT_RECIPIENT_CONFIG_PATH = "runtime/config/report_delivery_recipients.json"
DEFAULT_RECIPIENT_SOURCE = "db"
SUPPORTED_RECIPIENT_SOURCES = {"db", "json", "auto"}
DEFAULT_SEND_RESULT_FILENAME = "send_result.json"
DEFAULT_ATTACHMENT_SIZE_LIMIT_MB = 20
DEFAULT_RECIPIENTS = ["feng@cuidena.cn", "yufei@cuidena.cn", "qian@cuidena.cn"]
DEFAULT_REPORT_ROUTES = {
    "monthly_financial_close": ["internal", "shareholders", "accountant", "operations"],
    "weekly_business_review": ["internal", "operations", "shareholders"],
    "weekly_ads_optimization": ["internal", "operations", "ads_operator"],
}


class ReportEmailSendError(SellerDataPipelineError):
    """Raised when a report delivery pack cannot be sent."""


@dataclass(frozen=True)
class RecipientRoute:
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: str | None = None

    @property
    def all_recipients(self) -> list[str]:
        return _dedupe_emails([*self.to, *self.cc, *self.bcc])

    def to_dict(self) -> dict[str, Any]:
        return {
            "to": self.to,
            "cc": self.cc,
            "bcc": self.bcc,
            "reply_to": self.reply_to,
        }


@dataclass(frozen=True)
class SmtpEmailConfig:
    host: str
    port: int
    security: str
    username: str | None
    password: str | None
    from_email: str
    from_name: str | None
    reply_to: str | None
    timeout_seconds: int
    max_retries: int
    retry_delay_seconds: float = 2.0


@dataclass(frozen=True)
class AttachmentToSend:
    path: Path
    kind: str
    size_bytes: int

    def to_dict(self, *, root: Path | None = None) -> dict[str, Any]:
        path_text = str(_relative_or_absolute(self.path, root)) if root else str(self.path)
        return {"path": path_text, "kind": self.kind, "size_bytes": self.size_bytes}


@dataclass(frozen=True)
class ReportEmailSendResult:
    status: str
    dry_run: bool
    delivery_pack_dir: Path
    send_result_path: Path
    report_type: str
    audience: str
    subject: str
    recipients: RecipientRoute
    attachments: list[AttachmentToSend]
    message_id: str | None = None
    sent_at: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    error_message: str | None = None
    recipient_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "dry_run": self.dry_run,
            "delivery_pack_dir": str(self.delivery_pack_dir),
            "send_result_path": str(self.send_result_path),
            "report_type": self.report_type,
            "audience": self.audience,
            "subject": self.subject,
            "recipient_source": self.recipient_source,
            "recipients": self.recipients.to_dict(),
            "recipient_counts": {
                "to": len(self.recipients.to),
                "cc": len(self.recipients.cc),
                "bcc": len(self.recipients.bcc),
                "total": len(self.recipients.all_recipients),
            },
            "attachments": [
                attachment.to_dict(root=self.delivery_pack_dir) for attachment in self.attachments
            ],
            "message_id": self.message_id,
            "sent_at": self.sent_at,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "error_message": self.error_message,
        }


class ReportEmailSenderService:
    """Send a generated report delivery pack via SMTP."""

    def __init__(
        self,
        *,
        settings: Settings,
        smtp_factory: Callable[..., Any] | None = None,
        smtp_ssl_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._settings = settings
        self._smtp_factory = smtp_factory or smtplib.SMTP
        self._smtp_ssl_factory = smtp_ssl_factory or smtplib.SMTP_SSL

    def send_pack(
        self,
        *,
        delivery_pack_dir: str | Path,
        audience: str | None = None,
        recipient_config_path: str | Path = DEFAULT_RECIPIENT_CONFIG_PATH,
        recipient_source: str = DEFAULT_RECIPIENT_SOURCE,
        to_override: list[str] | None = None,
        cc_override: list[str] | None = None,
        bcc_override: list[str] | None = None,
        reply_to_override: str | None = None,
        allow_blocked: bool = False,
        force_resend: bool = False,
        max_attachment_mb: int = DEFAULT_ATTACHMENT_SIZE_LIMIT_MB,
        dry_run: bool = True,
    ) -> ReportEmailSendResult:
        pack_dir = Path(delivery_pack_dir)
        manifest_path = pack_dir / "delivery_manifest.json"
        if not manifest_path.exists():
            raise ReportEmailSendError(f"delivery_manifest.json not found: {manifest_path}")
        manifest = _load_json(manifest_path)
        report = _manifest_report(manifest)
        email = _manifest_email(manifest)
        report_type = _require_text(report.get("report_type"), "manifest.report.report_type")
        resolved_audience = audience or _require_text(
            email.get("audience"),
            "manifest.email.audience",
        )
        subject = _read_relative_text(
            pack_dir,
            _require_text(email.get("subject_path"), "subject_path"),
        )
        body_html = _read_relative_text(
            pack_dir,
            _require_text(email.get("body_html_path"), "body_html_path"),
        )
        body_text = _read_relative_text(
            pack_dir,
            _require_text(email.get("body_text_path"), "body_text_path"),
        )
        _validate_send_guard(manifest, allow_blocked=allow_blocked)
        send_result_path = pack_dir / DEFAULT_SEND_RESULT_FILENAME
        _validate_not_already_sent(send_result_path, force_resend=force_resend)
        recipients, resolved_recipient_source = self._resolve_recipients(
            report_type=report_type,
            audience=resolved_audience,
            recipient_config_path=recipient_config_path,
            recipient_source=recipient_source,
            to_override=to_override,
            cc_override=cc_override,
            bcc_override=bcc_override,
            reply_to_override=reply_to_override,
        )
        attachments = _resolve_attachments(pack_dir, manifest, max_attachment_mb=max_attachment_mb)
        smtp_config = None if dry_run else _smtp_config_from_settings(self._settings)
        message_id = make_msgid(
            domain=_message_id_domain(smtp_config.from_email if smtp_config else None)
        )
        result = ReportEmailSendResult(
            status="dry_run" if dry_run else "prepared",
            dry_run=dry_run,
            delivery_pack_dir=pack_dir,
            send_result_path=send_result_path,
            report_type=report_type,
            audience=resolved_audience,
            subject=subject.strip(),
            recipients=recipients,
            attachments=attachments,
            message_id=message_id,
            smtp_host=smtp_config.host if smtp_config else None,
            smtp_port=smtp_config.port if smtp_config else None,
            recipient_source=resolved_recipient_source,
        )
        if dry_run:
            _write_send_result(send_result_path, result)
            return result
        assert smtp_config is not None
        message = _build_email_message(
            smtp_config=smtp_config,
            recipients=recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            message_id=message_id,
        )
        try:
            self._send_with_retries(message, recipients=recipients, smtp_config=smtp_config)
        except Exception as exc:  # noqa: BLE001 - preserve the SMTP error in send_result.json.
            failed = ReportEmailSendResult(
                status="failed",
                dry_run=False,
                delivery_pack_dir=pack_dir,
                send_result_path=send_result_path,
                report_type=report_type,
                audience=resolved_audience,
                subject=subject.strip(),
                recipients=recipients,
                attachments=attachments,
                message_id=message_id,
                sent_at=None,
                smtp_host=smtp_config.host,
                smtp_port=smtp_config.port,
                error_message=str(exc),
                recipient_source=resolved_recipient_source,
            )
            _write_send_result(send_result_path, failed)
            raise ReportEmailSendError(f"SMTP send failed: {exc}") from exc
        sent = ReportEmailSendResult(
            status="sent",
            dry_run=False,
            delivery_pack_dir=pack_dir,
            send_result_path=send_result_path,
            report_type=report_type,
            audience=resolved_audience,
            subject=subject.strip(),
            recipients=recipients,
            attachments=attachments,
            message_id=message_id,
            sent_at=datetime.now(UTC).isoformat(),
            smtp_host=smtp_config.host,
            smtp_port=smtp_config.port,
            recipient_source=resolved_recipient_source,
        )
        _write_send_result(send_result_path, sent)
        return sent

    def _resolve_recipients(
        self,
        *,
        report_type: str,
        audience: str,
        recipient_config_path: str | Path,
        recipient_source: str,
        to_override: list[str] | None,
        cc_override: list[str] | None,
        bcc_override: list[str] | None,
        reply_to_override: str | None,
    ) -> tuple[RecipientRoute, str]:
        normalised_source = _normalise_recipient_source(recipient_source)
        if any([to_override, cc_override, bcc_override, reply_to_override]):
            route = RecipientRoute(
                to=_clean_email_list(to_override),
                cc=_clean_email_list(cc_override),
                bcc=_clean_email_list(bcc_override),
                reply_to=_clean_optional_email(reply_to_override),
            )
            _validate_recipients(route)
            return route, "override"

        route: RecipientRoute | None = None
        source_used: str | None = None
        if normalised_source in {"db", "auto"}:
            try:
                route = load_recipient_route_from_db(
                    settings=self._settings,
                    report_type=report_type,
                    audience=audience,
                )
                source_used = "db"
            except ReportEmailSendError:
                if normalised_source == "db":
                    raise

        if route is None and normalised_source in {"json", "auto"}:
            route = load_recipient_route(
                config_path=recipient_config_path,
                report_type=report_type,
                audience=audience,
            )
            source_used = "json"

        if route is None:
            raise ReportEmailSendError(
                f"No recipient route resolved for report_type={report_type} audience={audience}."
            )

        if not route.to and not route.cc and not route.bcc:
            fallback = _clean_email_list([self._settings.report_receiver_email])
            if fallback:
                route = RecipientRoute(to=fallback, reply_to=route.reply_to)
                source_used = "REPORT_RECEIVER_EMAIL"
        _validate_recipients(route)
        return route, source_used or normalised_source

    def _send_with_retries(
        self,
        message: EmailMessage,
        *,
        recipients: RecipientRoute,
        smtp_config: SmtpEmailConfig,
    ) -> None:
        attempts = max(1, smtp_config.max_retries + 1)
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                self._send_once(message, recipients=recipients, smtp_config=smtp_config)
                return
            except Exception as exc:  # noqa: BLE001 - retry and re-raise after final attempt.
                last_exc = exc
                if attempt >= attempts:
                    break
                sleep(smtp_config.retry_delay_seconds * attempt)
        if last_exc is not None:
            raise last_exc

    def _send_once(
        self,
        message: EmailMessage,
        *,
        recipients: RecipientRoute,
        smtp_config: SmtpEmailConfig,
    ) -> None:
        context = ssl.create_default_context()
        security = smtp_config.security.lower()
        if security == "ssl":
            with self._smtp_ssl_factory(
                smtp_config.host,
                smtp_config.port,
                timeout=smtp_config.timeout_seconds,
                context=context,
            ) as smtp:
                _smtp_login_if_needed(smtp, smtp_config)
                smtp.send_message(message, to_addrs=recipients.all_recipients)
            return
        with self._smtp_factory(
            smtp_config.host,
            smtp_config.port,
            timeout=smtp_config.timeout_seconds,
        ) as smtp:
            if security == "starttls":
                smtp.starttls(context=context)
            _smtp_login_if_needed(smtp, smtp_config)
            smtp.send_message(message, to_addrs=recipients.all_recipients)


def load_recipient_route_from_db(
    *,
    settings: Settings,
    report_type: str,
    audience: str,
) -> RecipientRoute:
    with get_connection(settings=settings, autocommit=True) as connection:
        repo = ReportEmailRecipientRepo(connection)
        rows = repo.fetch_enabled_recipients(report_type=report_type, audience=audience)
    if not rows:
        raise ReportEmailSendError(
            f"DB recipient route not found for report_type={report_type} audience={audience}."
        )
    return recipient_route_from_db_records(rows)


def recipient_route_from_db_records(rows: list[ReportEmailRecipientRecord]) -> RecipientRoute:
    to: list[str] = []
    cc: list[str] = []
    bcc: list[str] = []
    for row in rows:
        email = row.email.strip()
        if not email:
            continue
        recipient_type = row.recipient_type.lower().strip()
        if recipient_type == "to":
            to.append(email)
        elif recipient_type == "cc":
            cc.append(email)
        elif recipient_type == "bcc":
            bcc.append(email)
    return RecipientRoute(
        to=_dedupe_emails(to),
        cc=_dedupe_emails(cc),
        bcc=_dedupe_emails(bcc),
    )


def load_recipient_route(
    *,
    config_path: str | Path,
    report_type: str,
    audience: str,
) -> RecipientRoute:
    path = Path(config_path)
    if not path.exists():
        raise ReportEmailSendError(
            f"Recipient config not found: {path}. Create it or pass --to override."
        )
    config = _load_json(path)
    routes = config.get("routes")
    if not isinstance(routes, dict):
        raise ReportEmailSendError(f"Recipient config is missing routes object: {path}")
    report_routes = routes.get(report_type)
    if not isinstance(report_routes, dict):
        raise ReportEmailSendError(
            f"Recipient route not found for report_type={report_type} in {path}"
        )
    raw_route = report_routes.get(audience)
    if not isinstance(raw_route, dict):
        raise ReportEmailSendError(
            f"Recipient route not found for report_type={report_type} audience={audience} in {path}"
        )
    defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
    return RecipientRoute(
        to=_clean_email_list(raw_route.get("to")),
        cc=_clean_email_list(raw_route.get("cc")),
        bcc=_clean_email_list(raw_route.get("bcc")),
        reply_to=_clean_optional_email(raw_route.get("reply_to") or defaults.get("reply_to")),
    )


def write_default_recipient_config(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ReportEmailSendError(f"Recipient config already exists: {target}")
    routes: dict[str, dict[str, dict[str, list[str]]]] = {}
    for report_type, audiences in DEFAULT_REPORT_ROUTES.items():
        routes[report_type] = {
            audience: {"to": DEFAULT_RECIPIENTS, "cc": [], "bcc": []} for audience in audiences
        }
    payload = {
        "version": "v1.0",
        "defaults": {"reply_to": ""},
        "routes": routes,
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _normalise_recipient_source(value: str | None) -> str:
    source = (value or DEFAULT_RECIPIENT_SOURCE).strip().lower()
    if source not in SUPPORTED_RECIPIENT_SOURCES:
        supported = ", ".join(sorted(SUPPORTED_RECIPIENT_SOURCES))
        raise ReportEmailSendError(
            f"Unsupported recipient_source={value!r}. Supported values: {supported}."
        )
    return source


def _smtp_config_from_settings(settings: Settings) -> SmtpEmailConfig:
    host = settings.report_email_smtp_host
    from_email = settings.report_email_from or settings.report_email_smtp_username
    if not host:
        raise ReportEmailSendError("REPORT_EMAIL_SMTP_HOST is required for --execute.")
    if not from_email:
        raise ReportEmailSendError(
            "REPORT_EMAIL_FROM or REPORT_EMAIL_SMTP_USERNAME is required for --execute."
        )
    security = settings.report_email_smtp_security.lower()
    if security not in {"starttls", "ssl", "none"}:
        raise ReportEmailSendError(
            "REPORT_EMAIL_SMTP_SECURITY must be one of: starttls, ssl, none."
        )
    if bool(settings.report_email_smtp_username) != bool(settings.report_email_smtp_password):
        raise ReportEmailSendError(
            "REPORT_EMAIL_SMTP_USERNAME and REPORT_EMAIL_SMTP_PASSWORD must be provided together."
        )
    return SmtpEmailConfig(
        host=host,
        port=settings.report_email_smtp_port,
        security=security,
        username=settings.report_email_smtp_username,
        password=settings.report_email_smtp_password,
        from_email=from_email,
        from_name=settings.report_email_from_name,
        reply_to=settings.report_email_reply_to,
        timeout_seconds=settings.report_email_smtp_timeout_seconds,
        max_retries=settings.report_email_smtp_max_retries,
    )


def _build_email_message(
    *,
    smtp_config: SmtpEmailConfig,
    recipients: RecipientRoute,
    subject: str,
    body_text: str,
    body_html: str,
    attachments: list[AttachmentToSend],
    message_id: str,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject.strip()
    message["From"] = formataddr((smtp_config.from_name or "", smtp_config.from_email))
    if recipients.to:
        message["To"] = ", ".join(recipients.to)
    if recipients.cc:
        message["Cc"] = ", ".join(recipients.cc)
    reply_to = recipients.reply_to or smtp_config.reply_to
    if reply_to:
        message["Reply-To"] = reply_to
    message["Message-ID"] = message_id
    message.set_content(body_text)
    if body_html.strip():
        message.add_alternative(body_html, subtype="html")
    for attachment in attachments:
        content_type, _encoding = mimetypes.guess_type(attachment.path.name)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            attachment.path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment.path.name,
        )
    return message


def _resolve_attachments(
    pack_dir: Path,
    manifest: dict[str, Any],
    *,
    max_attachment_mb: int,
) -> list[AttachmentToSend]:
    raw_attachments = manifest.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReportEmailSendError("delivery_manifest.json is missing attachments list.")
    attachments: list[AttachmentToSend] = []
    total_size = 0
    for raw in raw_attachments:
        if not isinstance(raw, dict):
            continue
        pack_path = raw.get("pack_path")
        if not pack_path:
            if raw.get("required", True):
                raise ReportEmailSendError("A required attachment is missing pack_path.")
            continue
        path = Path(str(pack_path).replace("\\", "/"))
        if not path.is_absolute():
            path = pack_dir / path
        if not path.exists() or not path.is_file():
            if raw.get("required", True):
                raise ReportEmailSendError(f"Attachment file not found: {path}")
            continue
        size_bytes = path.stat().st_size
        total_size += size_bytes
        attachments.append(
            AttachmentToSend(
                path=path,
                kind=str(raw.get("kind") or "attachment"),
                size_bytes=size_bytes,
            )
        )
    max_bytes = max_attachment_mb * 1024 * 1024
    if total_size > max_bytes:
        raise ReportEmailSendError(
            f"Attachment total size {total_size} bytes exceeds limit {max_attachment_mb} MB."
        )
    return attachments


def _validate_send_guard(manifest: dict[str, Any], *, allow_blocked: bool) -> None:
    send_guard = manifest.get("send_guard")
    if not isinstance(send_guard, dict):
        raise ReportEmailSendError("delivery_manifest.json is missing send_guard object.")
    if send_guard.get("send_allowed") is not True and not allow_blocked:
        messages = send_guard.get("messages")
        message_text = (
            "; ".join(str(item) for item in messages) if isinstance(messages, list) else ""
        )
        raise ReportEmailSendError(
            "Delivery pack send_guard blocks sending. "
            f"Use --allow-blocked only for internal manual overrides. {message_text}"
        )


def _validate_not_already_sent(path: Path, *, force_resend: bool) -> None:
    if force_resend or not path.exists():
        return
    payload = _load_json(path)
    if payload.get("status") == "sent":
        raise ReportEmailSendError(
            f"This delivery pack already has status=sent at {path}. Use --force-resend to resend."
        )


def _validate_recipients(route: RecipientRoute) -> None:
    if not route.all_recipients:
        raise ReportEmailSendError("No recipients resolved. Configure route or pass --to.")
    invalid = [email for email in route.all_recipients if not _looks_like_email(email)]
    if invalid:
        raise ReportEmailSendError(f"Invalid recipient email(s): {', '.join(invalid)}")
    if route.reply_to and not _looks_like_email(route.reply_to):
        raise ReportEmailSendError(f"Invalid reply_to email: {route.reply_to}")


def _smtp_login_if_needed(smtp: Any, smtp_config: SmtpEmailConfig) -> None:
    if smtp_config.username and smtp_config.password:
        smtp.login(smtp_config.username, smtp_config.password)


def _manifest_report(manifest: dict[str, Any]) -> dict[str, Any]:
    report = manifest.get("report")
    if not isinstance(report, dict):
        raise ReportEmailSendError("delivery_manifest.json is missing report object.")
    return report


def _manifest_email(manifest: dict[str, Any]) -> dict[str, Any]:
    email = manifest.get("email")
    if not isinstance(email, dict):
        raise ReportEmailSendError("delivery_manifest.json is missing email object.")
    return email


def _read_relative_text(root: Path, relative_path: str) -> str:
    path = root / relative_path
    if not path.exists() or not path.is_file():
        raise ReportEmailSendError(f"Required email file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ReportEmailSendError(f"Required email file is empty: {path}")
    return text


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReportEmailSendError(f"Invalid JSON file: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReportEmailSendError(f"JSON root must be an object: {path}")
    return payload


def _write_send_result(path: Path, result: ReportEmailSendResult) -> None:
    path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReportEmailSendError(f"Required field is missing or empty: {field_name}")
    return value.strip()


def _clean_email_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace(";", ",").split(",")
    elif isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raw_items = [str(value)]
    return _dedupe_emails([item.strip() for item in raw_items if item.strip()])


def _clean_optional_email(value: Any) -> str | None:
    emails = _clean_email_list(value)
    return emails[0] if emails else None


def _dedupe_emails(emails: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for email in emails:
        key = email.lower()
        if key not in seen:
            unique.append(email)
            seen.add(key)
    return unique


def _looks_like_email(value: str) -> bool:
    return "@" in value and "." in value.rsplit("@", 1)[-1] and " " not in value


def _relative_or_absolute(path: Path, root: Path | None) -> Path:
    if root is None:
        return path
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _message_id_domain(from_email: str | None) -> str | None:
    if not from_email or "@" not in from_email:
        return None
    return from_email.rsplit("@", 1)[-1]
