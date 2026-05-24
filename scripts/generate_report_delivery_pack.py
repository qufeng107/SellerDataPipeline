from __future__ import annotations

import argparse
import json
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.services.report_delivery_service import (
    DEFAULT_DELIVERY_ROOT,
    ReportDeliveryPackService,
)
from seller_data_pipeline.services.report_delivery_templates import (
    AUDIENCES,
    SUPPORTED_REPORT_TYPES,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a local report delivery email draft pack from an existing report JSON. "
            "v1 writes subject/body/manifest/attachments only and never sends email."
        )
    )
    parser.add_argument("--report-json", required=True, help="Path to report JSON.")
    parser.add_argument(
        "--template",
        default="auto",
        choices=["auto", *sorted(SUPPORTED_REPORT_TYPES)],
        help="Template override. Defaults to auto by report_json.report_type.",
    )
    parser.add_argument(
        "--audience",
        default="internal",
        choices=sorted(AUDIENCES),
        help="Audience role. Default: internal.",
    )
    parser.add_argument("--xlsx-path", default=None, help="Optional XLSX attachment override.")
    parser.add_argument("--output-dir", default=None, help="Optional exact output directory.")
    parser.add_argument(
        "--output-root",
        default=DEFAULT_DELIVERY_ROOT,
        help="Output root. Default: runtime/report_delivery.",
    )
    parser.add_argument(
        "--include-json-attachment",
        action="store_true",
        help="Also copy the source JSON into attachments. Default is XLSX only.",
    )
    parser.add_argument(
        "--no-copy-attachments",
        action="store_true",
        help="Reference source attachments instead of copying them into the pack.",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow partial report status for audiences that would otherwise be blocked.",
    )
    parser.add_argument(
        "--allow-needs-review",
        action="store_true",
        help="Allow needs_review report status in send_guard. Use only for internal review.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Compatibility/safety flag. v1 never sends email; dry-run still writes local "
            "draft pack files for manual review."
        ),
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional extra JSON path with generation summary.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    service = ReportDeliveryPackService()
    result = service.generate_pack(
        report_json_path=args.report_json,
        template=args.template,
        audience=args.audience,
        xlsx_path=args.xlsx_path,
        output_dir=args.output_dir,
        output_root=args.output_root,
        include_json_attachment=args.include_json_attachment,
        copy_attachments=not args.no_copy_attachments,
        allow_partial=True if args.allow_partial else None,
        allow_needs_review=args.allow_needs_review,
        dry_run=True if args.dry_run else True,
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
        f"Report Delivery Pack status={result.status} dry_run={result.dry_run} report_type={result.report_type} "
        f"audience={result.audience} send_allowed={result.send_guard.send_allowed}"
    )
    print(f"output_dir={result.output_dir}")
    print(f"manifest={result.manifest_path}")
    print(f"subject={result.subject_path}")
    print(f"body_html={result.body_html_path}")
    print(f"body_text={result.body_text_path}")
    print(f"attachments={len(result.attachments)}")
    for attachment in result.attachments:
        print(f"- {attachment.kind}: source={attachment.source_path} pack={attachment.pack_path}")
    if result.send_guard.messages:
        print("send_guard_messages:")
        for message in result.send_guard.messages:
            print(f"- {message}")
    non_info_warnings = [
        warning for warning in result.warnings if warning.get("severity") != "info"
    ]
    print(f"warnings={len(result.warnings)} non_info_warnings={len(non_info_warnings)}")


if __name__ == "__main__":
    run_cli_main(main)
