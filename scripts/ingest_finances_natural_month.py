from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.finances_transaction_repo import FinancesTransactionRepo
from seller_data_pipeline.integrations.amazon.sp_api_client import AmazonSpApiClient
from seller_data_pipeline.services.finances_natural_month_service import (
    natural_month_utc_fetch_window,
    prepare_natural_month_transactions,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Finances API transactions, normalize them to the marketplace local calendar "
            "month and optionally upsert the guarded v1.90 natural-month ledger."
        )
    )
    parser.add_argument("--marketplace-id", default=None)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--output-root", default="runtime/ingestion/finances_api")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--allow-review",
        action="store_true",
        help="Allow execution when any normalized row is marked review_required.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID")
    start_date, end_date = _month_range(args.month)
    fetch_after, fetch_before, timezone_name = natural_month_utc_fetch_window(
        marketplace_id=marketplace_id,
        start_date=start_date,
        end_date=end_date,
    )
    latest_allowed = datetime.now(tz=UTC) - timedelta(minutes=2, seconds=5)
    fetch_before = min(fetch_before, latest_allowed)
    if fetch_before <= fetch_after:
        raise SystemExit("Finances API window is too recent; retry after the safety delay")

    client = AmazonSpApiClient(settings=settings)
    transactions: list[dict] = []
    pages: list[dict] = []
    next_token = None
    for page_number in range(1, args.max_pages + 1):
        response = client.list_finance_transactions(
            posted_after=fetch_after,
            posted_before=fetch_before,
            marketplace_id=marketplace_id,
            next_token=next_token,
        )
        pages.append(response)
        payload = response.get("payload") or {}
        page_transactions = payload.get("transactions") or []
        if not isinstance(page_transactions, list):
            raise RuntimeError("Finances API payload.transactions is not a list")
        transactions.extend(page_transactions)
        next_token = payload.get("nextToken")
        if not next_token:
            break
    else:
        raise RuntimeError(f"Finances API pagination exceeded max_pages={args.max_pages}")

    prepared = prepare_natural_month_transactions(
        transactions,
        marketplace_id=marketplace_id,
        start_date=start_date,
        end_date=end_date,
        pages_fetched=len(pages),
        fetched_transaction_count=len(transactions),
    )
    output_dir = Path(args.output_root) / marketplace_id / args.month
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "raw_pages.json", pages)
    _write_json(output_dir / "summary.json", prepared.compact_summary())
    _write_json(
        output_dir / "prepared_rows.json",
        [row.to_db_row() for row in prepared.rows],
    )

    print(
        "FINANCES_NATURAL_MONTH "
        f"marketplace_id={marketplace_id} month={args.month} timezone={timezone_name} "
        f"pages={len(pages)} fetched={len(transactions)} local_rows={len(prepared.rows)} "
        f"review_required={prepared.review_required_count} "
        f"review_amount={prepared.review_required_amount}"
    )
    print(
        "FINANCES_NATURAL_MONTH_SUMMARY_JSON="
        + json.dumps(prepared.compact_summary(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )

    if not args.execute:
        print(f"Finances natural-month ingestion mode=dry_run output_dir={output_dir}")
        return
    if prepared.review_required_count and not args.allow_review:
        raise SystemExit(
            "Blocked Finances natural-month SQL write: one or more rows require review"
        )

    with get_connection(settings=settings, autocommit=False) as connection:
        repo = FinancesTransactionRepo(connection)
        try:
            result = repo.upsert_rows([row.to_db_row() for row in prepared.rows])
            repo.commit()
        except Exception:
            connection.rollback()
            raise

    print(
        "Finances natural-month ingestion mode=execute status=success "
        f"attempted={result.attempted_rows} inserted={result.inserted_rows} "
        f"updated={result.updated_rows} written={result.written_rows} skipped={result.skipped_rows}"
    )


def _month_range(month: str) -> tuple[date, date]:
    try:
        year_text, month_text = month.split("-", 1)
        start = date(int(year_text), int(month_text), 1)
    except (ValueError, TypeError) as exc:
        raise SystemExit("--month must be YYYY-MM") from exc
    if start.month == 12:
        next_month = date(start.year + 1, 1, 1)
    else:
        next_month = date(start.year, start.month + 1, 1)
    return start, next_month - timedelta(days=1)


def _json_ready(value):
    from decimal import Decimal
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    return value


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(_json_ready(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    run_cli_main(main)
