from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

from seller_data_pipeline.integrations.amazon.sp_api_client import AmazonSpApiClient

ZERO = Decimal("0")


@dataclass(frozen=True)
class FinancesTransactionsSampleResult:
    marketplace_id: str
    start_date: date
    end_date: date
    transaction_status_filter: str | None
    pages_fetched: int
    transaction_count: int
    output_dir: Path
    combined_path: Path
    summary_path: Path
    summary: dict[str, Any]


def sample_finances_transactions(
    *,
    client: AmazonSpApiClient,
    marketplace_id: str,
    start_date: date,
    end_date: date,
    transaction_status: str | None = None,
    output_root: str | Path = "runtime/sampling/finances_api",
    max_pages: int = 100,
    now: datetime | None = None,
) -> FinancesTransactionsSampleResult:
    """Fetch and archive a read-only Finances API transaction sample.

    This is intentionally an exploratory/raw capability in v1.89. It does not write to Azure SQL
    and does not alter Monthly Financial Close calculations. Raw API pages are preserved so the
    real response can be reconciled against Seller Central before any normalized schema is frozen.
    """

    if not marketplace_id:
        raise ValueError("marketplace_id is required")
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")

    requested_after = datetime.combine(start_date, time.min, tzinfo=UTC)
    requested_before = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
    current_time = (now or datetime.now(tz=UTC)).astimezone(UTC)
    latest_allowed_before = current_time - timedelta(minutes=2, seconds=5)
    effective_before = min(requested_before, latest_allowed_before)
    if effective_before <= requested_after:
        raise ValueError(
            "requested period is too recent for Finances API postedBefore; "
            "wait until more than two minutes after the period begins"
        )
    if effective_before - requested_after > timedelta(days=180):
        raise ValueError("Finances API postedAfter/postedBefore window cannot exceed 180 days")

    output_dir = Path(output_root) / marketplace_id / f"{start_date.isoformat()}_{end_date.isoformat()}"
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    pages: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []
    next_token: str | None = None

    for page_number in range(1, max_pages + 1):
        response = client.list_finance_transactions(
            posted_after=requested_after,
            posted_before=effective_before,
            marketplace_id=marketplace_id,
            transaction_status=transaction_status,
            next_token=next_token,
        )
        pages.append(response)
        _write_json(pages_dir / f"page_{page_number:03d}.json", response)

        payload = response.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, Mapping):
            raise ValueError("Finances API response payload must be an object")

        page_transactions = payload.get("transactions") or []
        if not isinstance(page_transactions, list):
            raise ValueError("Finances API payload.transactions must be a list")
        for transaction in page_transactions:
            if not isinstance(transaction, dict):
                raise ValueError("Finances API transaction must be an object")
            transactions.append(transaction)

        raw_next_token = payload.get("nextToken")
        next_token = str(raw_next_token) if raw_next_token else None
        if not next_token:
            break
    else:
        raise RuntimeError(
            f"Finances API pagination exceeded max_pages={max_pages}; refusing partial silent sample"
        )

    combined = {
        "marketplace_id": marketplace_id,
        "requested_start_date": start_date.isoformat(),
        "requested_end_date": end_date.isoformat(),
        "posted_after": requested_after.isoformat().replace("+00:00", "Z"),
        "posted_before": effective_before.isoformat().replace("+00:00", "Z"),
        "posted_before_was_clamped": effective_before != requested_before,
        "transaction_status_filter": transaction_status,
        "pages_fetched": len(pages),
        "transactions": transactions,
    }
    combined_path = output_dir / "transactions.json"
    _write_json(combined_path, combined)

    summary = summarize_finances_transactions(
        transactions,
        marketplace_id=marketplace_id,
        start_date=start_date,
        end_date=end_date,
        pages_fetched=len(pages),
        transaction_status_filter=transaction_status,
        posted_before_was_clamped=effective_before != requested_before,
    )
    summary_path = output_dir / "summary.json"
    _write_json(summary_path, summary)

    return FinancesTransactionsSampleResult(
        marketplace_id=marketplace_id,
        start_date=start_date,
        end_date=end_date,
        transaction_status_filter=transaction_status,
        pages_fetched=len(pages),
        transaction_count=len(transactions),
        output_dir=output_dir,
        combined_path=combined_path,
        summary_path=summary_path,
        summary=summary,
    )


def summarize_finances_transactions(
    transactions: Iterable[Mapping[str, Any]],
    *,
    marketplace_id: str,
    start_date: date,
    end_date: date,
    pages_fetched: int,
    transaction_status_filter: str | None,
    posted_before_was_clamped: bool = False,
) -> dict[str, Any]:
    rows = list(transactions)
    status_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    description_counts: Counter[str] = Counter()
    related_identifier_counts: Counter[str] = Counter()
    settlement_ids: set[str] = set()
    transaction_key_counts: Counter[str] = Counter()
    item_key_counts: Counter[str] = Counter()
    context_type_counts: Counter[str] = Counter()
    breakdown_type_counts: Counter[str] = Counter()
    transaction_ids: Counter[str] = Counter()
    total_amounts_by_currency: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    total_amounts_by_type_currency: defaultdict[tuple[str, str], Decimal] = defaultdict(
        lambda: ZERO
    )
    total_amounts_by_status_currency: defaultdict[tuple[str, str], Decimal] = defaultdict(
        lambda: ZERO
    )
    breakdown_leaf_totals: defaultdict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
    item_count = 0

    for transaction in rows:
        transaction_key_counts.update(str(key) for key in transaction)
        transaction_id = _text(transaction.get("transactionId"))
        if transaction_id:
            transaction_ids[transaction_id] += 1

        status = _text(transaction.get("transactionStatus")) or "<missing>"
        transaction_type = _text(transaction.get("transactionType")) or "<missing>"
        description = _text(transaction.get("description")) or "<missing>"
        status_counts[status] += 1
        type_counts[transaction_type] += 1
        description_counts[description] += 1

        currency, amount = _currency(transaction.get("totalAmount"))
        if currency and amount is not None:
            total_amounts_by_currency[currency] += amount
            total_amounts_by_type_currency[(transaction_type, currency)] += amount
            total_amounts_by_status_currency[(status, currency)] += amount

        for identifier in _list_of_mappings(transaction.get("relatedIdentifiers")):
            name = _text(identifier.get("relatedIdentifierName")) or "<missing>"
            value = _text(identifier.get("relatedIdentifierValue"))
            related_identifier_counts[name] += 1
            if name == "SETTLEMENT_ID" and value:
                settlement_ids.add(value)

        _accumulate_breakdown_leaves(
            transaction.get("breakdowns"),
            scope="transaction",
            path=(),
            totals=breakdown_leaf_totals,
            type_counts=breakdown_type_counts,
        )

        for item in _list_of_mappings(transaction.get("items")):
            item_count += 1
            item_key_counts.update(str(key) for key in item)
            _accumulate_breakdown_leaves(
                item.get("breakdowns"),
                scope="item",
                path=(),
                totals=breakdown_leaf_totals,
                type_counts=breakdown_type_counts,
            )
            for context in _list_of_mappings(item.get("contexts")):
                context_type_counts[_text(context.get("contextType")) or "<missing>"] += 1
        for context in _list_of_mappings(transaction.get("contexts")):
            context_type_counts[_text(context.get("contextType")) or "<missing>"] += 1

    duplicate_ids = {key: count for key, count in transaction_ids.items() if count > 1}

    return {
        "schema_version": "v1.89-finances-api-sampling",
        "marketplace_id": marketplace_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "transaction_status_filter": transaction_status_filter,
        "posted_before_was_clamped": posted_before_was_clamped,
        "pages_fetched": pages_fetched,
        "transaction_count": len(rows),
        "unique_transaction_id_count": len(transaction_ids),
        "duplicate_transaction_ids": duplicate_ids,
        "item_count": item_count,
        "status_counts": _sorted_counter(status_counts),
        "transaction_type_counts": _sorted_counter(type_counts),
        "description_counts": _sorted_counter(description_counts),
        "related_identifier_name_counts": _sorted_counter(related_identifier_counts),
        "settlement_ids": sorted(settlement_ids),
        "total_amounts_by_currency": _decimal_mapping(total_amounts_by_currency),
        "total_amounts_by_transaction_type_currency": _decimal_tuple_mapping(
            total_amounts_by_type_currency
        ),
        "total_amounts_by_status_currency": _decimal_tuple_mapping(total_amounts_by_status_currency),
        "breakdown_leaf_totals": _decimal_tuple_mapping(breakdown_leaf_totals),
        "observed_transaction_keys": sorted(transaction_key_counts),
        "observed_item_keys": sorted(item_key_counts),
        "observed_context_types": sorted(context_type_counts),
        "observed_breakdown_types": sorted(breakdown_type_counts),
    }


def compact_finances_summary(summary: Mapping[str, Any], *, top_breakdowns: int = 30) -> dict[str, Any]:
    breakdowns = summary.get("breakdown_leaf_totals") or {}
    if isinstance(breakdowns, Mapping):
        breakdown_items = sorted(
            breakdowns.items(),
            key=lambda item: abs(_decimal(item[1]) or ZERO),
            reverse=True,
        )[:top_breakdowns]
        compact_breakdowns = dict(breakdown_items)
    else:
        compact_breakdowns = {}
    return {
        "schema_version": summary.get("schema_version"),
        "marketplace_id": summary.get("marketplace_id"),
        "start_date": summary.get("start_date"),
        "end_date": summary.get("end_date"),
        "pages_fetched": summary.get("pages_fetched"),
        "transaction_count": summary.get("transaction_count"),
        "unique_transaction_id_count": summary.get("unique_transaction_id_count"),
        "duplicate_transaction_ids": summary.get("duplicate_transaction_ids"),
        "item_count": summary.get("item_count"),
        "status_counts": summary.get("status_counts"),
        "transaction_type_counts": summary.get("transaction_type_counts"),
        "settlement_ids": summary.get("settlement_ids"),
        "total_amounts_by_currency": summary.get("total_amounts_by_currency"),
        "total_amounts_by_transaction_type_currency": summary.get(
            "total_amounts_by_transaction_type_currency"
        ),
        "top_breakdown_leaf_totals": compact_breakdowns,
        "observed_breakdown_types": summary.get("observed_breakdown_types"),
        "posted_before_was_clamped": summary.get("posted_before_was_clamped"),
    }


def _accumulate_breakdown_leaves(
    value: Any,
    *,
    scope: str,
    path: tuple[str, ...],
    totals: defaultdict[tuple[str, str], Decimal],
    type_counts: Counter[str],
) -> None:
    for breakdown in _list_of_mappings(value):
        breakdown_type = _text(breakdown.get("breakdownType")) or "<missing>"
        type_counts[breakdown_type] += 1
        current_path = (*path, breakdown_type)
        children = _list_of_mappings(breakdown.get("breakdowns"))
        if children:
            _accumulate_breakdown_leaves(
                children,
                scope=scope,
                path=current_path,
                totals=totals,
                type_counts=type_counts,
            )
            continue
        currency, amount = _currency(breakdown.get("breakdownAmount"))
        if currency and amount is not None:
            totals[(f"{scope}:{'/'.join(current_path)}", currency)] += amount


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _currency(value: Any) -> tuple[str | None, Decimal | None]:
    if not isinstance(value, Mapping):
        return None, None
    currency = _text(value.get("currencyCode"))
    amount = _decimal(value.get("currencyAmount"))
    return currency, amount


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _decimal_mapping(values: Mapping[str, Decimal]) -> dict[str, str]:
    return {key: _decimal_text(value) for key, value in sorted(values.items())}


def _decimal_tuple_mapping(values: Mapping[tuple[str, str], Decimal]) -> dict[str, str]:
    return {
        f"{key[0]}|{key[1]}": _decimal_text(value)
        for key, value in sorted(values.items(), key=lambda item: item[0])
    }


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


__all__ = [
    "FinancesTransactionsSampleResult",
    "compact_finances_summary",
    "sample_finances_transactions",
    "summarize_finances_transactions",
]
