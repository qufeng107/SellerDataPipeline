from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.integrations.amazon.sp_api_client import FINANCES_TRANSACTION_STATUSES
from seller_data_pipeline.services.finances_transactions_sampling_service import (
    compact_finances_summary,
    sample_finances_transactions,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Finances API v2024-06-19 transaction sampler. "
            "Writes raw pages + combined transactions + schema/breakdown summary; no SQL writes."
        )
    )
    parser.add_argument("--marketplace-id", default=None)
    parser.add_argument("--month", default=None, help="YYYY-MM. Mutually exclusive with date range.")
    parser.add_argument("--start-date", default=None, help="Inclusive YYYY-MM-DD.")
    parser.add_argument("--end-date", default=None, help="Inclusive YYYY-MM-DD.")
    parser.add_argument(
        "--transaction-status",
        choices=sorted(FINANCES_TRANSACTION_STATUSES),
        default=None,
        help="Optional Amazon transaction status filter; default samples all statuses.",
    )
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument(
        "--output-root",
        default="runtime/sampling/finances_api",
        help="Local artifact root. Raw financial data must not be committed to Git.",
    )
    parser.add_argument(
        "--top-breakdowns",
        type=int,
        default=30,
        help="Maximum breakdown leaf totals included in the compact log summary.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")

    start_date, end_date = _resolve_window(
        month=args.month,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    result = sample_finances_transactions(
        client=_client(settings),
        marketplace_id=marketplace_id,
        start_date=start_date,
        end_date=end_date,
        transaction_status=args.transaction_status,
        output_root=args.output_root,
        max_pages=args.max_pages,
    )

    print(
        "FINANCES_SAMPLE "
        f"marketplace_id={marketplace_id} period={start_date}..{end_date} "
        f"pages={result.pages_fetched} transactions={result.transaction_count}"
    )
    print(f"FINANCES_SAMPLE_COMBINED={result.combined_path}")
    print(f"FINANCES_SAMPLE_SUMMARY_PATH={result.summary_path}")
    print(
        "FINANCES_SAMPLE_SUMMARY_JSON="
        + json.dumps(
            compact_finances_summary(result.summary, top_breakdowns=args.top_breakdowns),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _client(settings):
    # Local import keeps CLI startup and --help independent of external HTTP calls.
    from seller_data_pipeline.integrations.amazon.sp_api_client import AmazonSpApiClient

    return AmazonSpApiClient(settings=settings)


def _resolve_window(
    *, month: str | None, start_date: str | None, end_date: str | None
) -> tuple[date, date]:
    if month:
        if start_date or end_date:
            raise SystemExit("--month cannot be combined with --start-date/--end-date")
        try:
            year_text, month_text = month.split("-", maxsplit=1)
            year = int(year_text)
            month_number = int(month_text)
            start = date(year, month_number, 1)
        except (TypeError, ValueError) as exc:
            raise SystemExit("--month must be YYYY-MM") from exc
        next_month = (
            date(year + 1, 1, 1) if month_number == 12 else date(year, month_number + 1, 1)
        )
        return start, next_month - timedelta(days=1)

    if not start_date or not end_date:
        raise SystemExit("Provide --month or both --start-date and --end-date")
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise SystemExit("--start-date/--end-date must be YYYY-MM-DD") from exc
    if end < start:
        raise SystemExit("--end-date must be on or after --start-date")
    return start, end


if __name__ == "__main__":
    run_cli_main(main)
