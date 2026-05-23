from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.db.repositories.report_email_recipient_repo import (
    ReportEmailRecipientRecord,
)
from seller_data_pipeline.services.report_email_sender import (
    DEFAULT_RECIPIENTS,
    ReportEmailSendError,
    ReportEmailSenderService,
    load_recipient_route,
    recipient_route_from_db_records,
    write_default_recipient_config,
)


def test_write_default_recipient_config_and_load_route(tmp_path: Path) -> None:
    config_path = tmp_path / "runtime" / "config" / "report_delivery_recipients.json"

    written = write_default_recipient_config(config_path)
    route = load_recipient_route(
        config_path=written,
        report_type="weekly_ads_optimization",
        audience="ads_operator",
    )

    assert route.to == DEFAULT_RECIPIENTS
    assert route.cc == []
    assert route.bcc == []


def test_recipient_route_from_db_records_groups_and_dedupes() -> None:
    rows = [
        ReportEmailRecipientRecord("*", "*", "to", "feng@cuidena.cn", "Feng", 10, 4),
        ReportEmailRecipientRecord("*", "*", "to", "feng@cuidena.cn", "Feng", 10, 4),
        ReportEmailRecipientRecord("*", "*", "cc", "qian@cuidena.cn", "Qian", 20, 4),
        ReportEmailRecipientRecord("*", "*", "bcc", "yufei@cuidena.cn", "Yufei", 30, 4),
    ]

    route = recipient_route_from_db_records(rows)

    assert route.to == ["feng@cuidena.cn"]
    assert route.cc == ["qian@cuidena.cn"]
    assert route.bcc == ["yufei@cuidena.cn"]


def test_send_pack_dry_run_writes_result(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path)
    config_path = _write_recipient_config(tmp_path)
    service = ReportEmailSenderService(settings=Settings())

    result = service.send_pack(
        delivery_pack_dir=pack_dir,
        recipient_config_path=config_path,
        recipient_source="json",
        dry_run=True,
    )

    assert result.status == "dry_run"
    assert result.recipients.to == ["feng@cuidena.cn", "yufei@cuidena.cn", "qian@cuidena.cn"]
    assert result.send_result_path.exists()
    payload = json.loads(result.send_result_path.read_text(encoding="utf-8"))
    assert payload["status"] == "dry_run"
    assert payload["recipient_counts"]["total"] == 3


def test_send_pack_uses_to_override_without_recipient_config(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path)
    service = ReportEmailSenderService(settings=Settings())

    result = service.send_pack(
        delivery_pack_dir=pack_dir,
        recipient_config_path=tmp_path / "missing.json",
        to_override=["test@example.com"],
        dry_run=True,
    )

    assert result.recipients.to == ["test@example.com"]


def test_blocked_manifest_fails_unless_allowed(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path, send_allowed=False)
    config_path = _write_recipient_config(tmp_path)
    service = ReportEmailSenderService(settings=Settings())

    try:
        service.send_pack(
            delivery_pack_dir=pack_dir,
            recipient_config_path=config_path,
            recipient_source="json",
            dry_run=True,
        )
    except ReportEmailSendError as exc:
        assert "send_guard blocks" in str(exc)
    else:
        raise AssertionError("Expected blocked send_guard to fail")

    allowed = service.send_pack(
        delivery_pack_dir=pack_dir,
        recipient_config_path=config_path,
        recipient_source="json",
        allow_blocked=True,
        dry_run=True,
    )
    assert allowed.status == "dry_run"


def test_execute_sends_with_fake_smtp(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path)
    config_path = _write_recipient_config(tmp_path)
    fake_smtp = _FakeSMTPFactory()
    settings = Settings(
        report_email_smtp_host="smtp.example.com",
        report_email_smtp_port=587,
        report_email_smtp_security="starttls",
        report_email_smtp_username="reports@example.com",
        report_email_smtp_password="secret",
        report_email_from="reports@example.com",
    )
    service = ReportEmailSenderService(settings=settings, smtp_factory=fake_smtp)

    result = service.send_pack(
        delivery_pack_dir=pack_dir,
        recipient_config_path=config_path,
        recipient_source="json",
        dry_run=False,
    )

    assert result.status == "sent"
    assert fake_smtp.instances[0].started_tls is True
    assert fake_smtp.instances[0].login_args == ("reports@example.com", "secret")
    assert fake_smtp.instances[0].sent_to == [
        "feng@cuidena.cn",
        "yufei@cuidena.cn",
        "qian@cuidena.cn",
    ]
    assert json.loads(result.send_result_path.read_text(encoding="utf-8"))["status"] == "sent"


def test_execute_requires_smtp_config(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path)
    config_path = _write_recipient_config(tmp_path)
    service = ReportEmailSenderService(settings=Settings())

    try:
        service.send_pack(
            delivery_pack_dir=pack_dir,
            recipient_config_path=config_path,
            recipient_source="json",
            dry_run=False,
        )
    except ReportEmailSendError as exc:
        assert "REPORT_EMAIL_SMTP_HOST" in str(exc)
    else:
        raise AssertionError("Expected missing SMTP host to fail")


def _write_recipient_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "recipients.json"
    config_path.write_text(
        json.dumps(
            {
                "version": "v1.0",
                "routes": {
                    "weekly_ads_optimization": {
                        "ads_operator": {
                            "to": [
                                "feng@cuidena.cn",
                                "yufei@cuidena.cn",
                                "qian@cuidena.cn",
                            ],
                            "cc": [],
                            "bcc": [],
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _write_pack(tmp_path: Path, *, send_allowed: bool = True) -> Path:
    pack_dir = tmp_path / "pack"
    attachments_dir = pack_dir / "attachments"
    attachments_dir.mkdir(parents=True)
    (pack_dir / "email_subject.txt").write_text("[Ads Optimization] Test\n", encoding="utf-8")
    (pack_dir / "email_body.html").write_text("<p>Hello</p>", encoding="utf-8")
    (pack_dir / "email_body.txt").write_text("Hello", encoding="utf-8")
    (attachments_dir / "weekly_ads_optimization.xlsx").write_bytes(b"fake workbook")
    manifest = {
        "delivery_type": "report_email_pack",
        "report": {
            "report_type": "weekly_ads_optimization",
            "status": "ok",
            "marketplace_id": "ATVPDKIKX0DER",
            "profile_id": "3917953989967300",
        },
        "email": {
            "audience": "ads_operator",
            "subject_path": "email_subject.txt",
            "body_html_path": "email_body.html",
            "body_text_path": "email_body.txt",
        },
        "attachments": [
            {
                "kind": "xlsx",
                "pack_path": "attachments/weekly_ads_optimization.xlsx",
                "required": True,
            }
        ],
        "send_guard": {
            "send_allowed": send_allowed,
            "severity": "ok" if send_allowed else "blocked",
            "messages": [] if send_allowed else ["blocked for test"],
        },
    }
    (pack_dir / "delivery_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pack_dir


class _FakeSMTP:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.sent_to: list[str] = []

    def __enter__(self) -> _FakeSMTP:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def starttls(self, *, context: Any) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message: Any, *, to_addrs: list[str]) -> None:
        self.sent_to = to_addrs


class _FakeSMTPFactory:
    def __init__(self) -> None:
        self.instances: list[_FakeSMTP] = []

    def __call__(self, *args: Any, **kwargs: Any) -> _FakeSMTP:
        instance = _FakeSMTP(*args, **kwargs)
        self.instances.append(instance)
        return instance
