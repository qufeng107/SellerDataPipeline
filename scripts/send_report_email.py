from __future__ import annotations

import argparse
import json
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.services.report_email_sender import (
    DEFAULT_ATTACHMENT_SIZE_LIMIT_MB,
    DEFAULT_RECIPIENT_CONFIG_PATH,
    DEFAULT_RECIPIENT_SOURCE,
    ReportEmailSenderService,
    write_default_recipient_config,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Send an existing report delivery pack via SMTP. Use --dry-run to validate the "
            "pack, recipients, attachments and manifest without sending."
        )
    )
    parser.add_argument(
        "--delivery-pack",
        help=(
            "Path to a generated report delivery pack directory containing delivery_manifest.json."
        ),
    )
    parser.add_argument(
        "--audience",
        default=None,
        help=(
            "Optional audience override. Defaults to the audience stored in delivery_manifest.json."
        ),
    )
    parser.add_argument(
        "--recipient-source",
        choices=["db", "json", "auto"],
        default=DEFAULT_RECIPIENT_SOURCE,
        help=(
            "Recipient routing source. Default: db. Use json for local runtime config "
            "or auto to try DB then JSON fallback."
        ),
    )
    parser.add_argument(
        "--recipient-config",
        default=DEFAULT_RECIPIENT_CONFIG_PATH,
        help=(
            "Fallback/local recipient routing config JSON. Default: "
            "runtime/config/report_delivery_recipients.json."
        ),
    )
    parser.add_argument(
        "--to",
        action="append",
        default=None,
        help="Recipient override. Repeatable.",
    )
    parser.add_argument("--cc", action="append", default=None, help="CC override. Repeatable.")
    parser.add_argument("--bcc", action="append", default=None, help="BCC override. Repeatable.")
    parser.add_argument("--reply-to", default=None, help="Reply-To override.")
    parser.add_argument(
        "--max-attachment-mb",
        type=int,
        default=DEFAULT_ATTACHMENT_SIZE_LIMIT_MB,
        help="Maximum total attachment size in MB. Default: 20.",
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Override delivery_manifest send_guard. Use only for internal manual review sends.",
    )
    parser.add_argument(
        "--force-resend",
        action="store_true",
        help="Allow sending again when send_result.json already has status=sent.",
    )
    parser.add_argument(
        "--init-recipient-config",
        action="store_true",
        help=(
            "Create the default local recipient config with current Cuidena recipients, then exit. "
            "The file is under runtime/ and should not be committed."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and write send_result.json without connecting to SMTP.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually send the email via SMTP. Mutually exclusive with --dry-run.",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional extra JSON path with send summary.",
    )
    args = parser.parse_args()

    if args.dry_run and args.execute:
        parser.error("Use either --dry-run or --execute, not both.")
    if args.init_recipient_config:
        path = write_default_recipient_config(args.recipient_config)
        print(f"created_recipient_config={path}")
        return
    if not args.delivery_pack:
        parser.error("--delivery-pack is required unless --init-recipient-config is used.")
    dry_run = not args.execute
    settings = get_settings()
    configure_logging(settings.log_level)
    service = ReportEmailSenderService(settings=settings)
    result = service.send_pack(
        delivery_pack_dir=args.delivery_pack,
        audience=args.audience,
        recipient_config_path=args.recipient_config,
        recipient_source=args.recipient_source,
        to_override=args.to,
        cc_override=args.cc,
        bcc_override=args.bcc,
        reply_to_override=args.reply_to,
        allow_blocked=args.allow_blocked,
        force_resend=args.force_resend,
        max_attachment_mb=args.max_attachment_mb,
        dry_run=dry_run,
    )
    payload = result.to_dict()
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        f"Report Email Send status={result.status} dry_run={result.dry_run} report_type={result.report_type} "
        f"audience={result.audience} recipients={len(result.recipients.all_recipients)} attachments={len(result.attachments)}"
    )
    print(f"recipient_source={result.recipient_source}")
    print(f"delivery_pack={result.delivery_pack_dir}")
    print(f"send_result={result.send_result_path}")
    print(f"subject={result.subject}")
    print(f"to={', '.join(result.recipients.to) if result.recipients.to else '-'}")
    print(f"cc={', '.join(result.recipients.cc) if result.recipients.cc else '-'}")
    print(f"bcc_count={len(result.recipients.bcc)}")
    for attachment in result.attachments:
        print(f"- attachment: {attachment.path} size_bytes={attachment.size_bytes}")
    if result.message_id:
        print(f"message_id={result.message_id}")
    if result.sent_at:
        print(f"sent_at={result.sent_at}")


if __name__ == "__main__":
    run_cli_main(main)
