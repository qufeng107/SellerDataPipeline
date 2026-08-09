from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from seller_data_pipeline.services.finances_transactions_sampling_service import (
    compact_finances_summary,
    sample_finances_transactions,
    summarize_finances_transactions,
)


class FakeFinancesClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def list_finance_transactions(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _transaction(
    transaction_id: str,
    *,
    status: str,
    transaction_type: str,
    amount: str,
    settlement_id: str,
) -> dict[str, Any]:
    return {
        "transactionId": transaction_id,
        "transactionStatus": status,
        "transactionType": transaction_type,
        "description": "Order Payment",
        "postedDate": "2026-07-05T12:00:00Z",
        "totalAmount": {"currencyCode": "USD", "currencyAmount": amount},
        "relatedIdentifiers": [
            {"relatedIdentifierName": "SETTLEMENT_ID", "relatedIdentifierValue": settlement_id},
            {"relatedIdentifierName": "ORDER_ID", "relatedIdentifierValue": "order-1"},
        ],
        "breakdowns": [
            {
                "breakdownType": "Sales",
                "breakdownAmount": {"currencyCode": "USD", "currencyAmount": amount},
                "breakdowns": [
                    {
                        "breakdownType": "Principal",
                        "breakdownAmount": {
                            "currencyCode": "USD",
                            "currencyAmount": amount,
                        },
                    }
                ],
            }
        ],
        "items": [
            {
                "description": "sample item",
                "contexts": [
                    {
                        "contextType": "ProductContext",
                        "sku": "W1-L6JP-TECU",
                        "quantityShipped": 1,
                    }
                ],
                "breakdowns": [
                    {
                        "breakdownType": "FBAFee",
                        "breakdownAmount": {
                            "currencyCode": "USD",
                            "currencyAmount": "-4.05",
                        },
                    }
                ],
            }
        ],
    }


def test_sample_finances_transactions_paginates_and_writes_raw_artifacts(tmp_path: Path) -> None:
    client = FakeFinancesClient(
        [
            {
                "payload": {
                    "transactions": [
                        _transaction(
                            "tx-1",
                            status="RELEASED",
                            transaction_type="Shipment",
                            amount="25.00",
                            settlement_id="26834303761",
                        )
                    ],
                    "nextToken": "next-1",
                }
            },
            {
                "payload": {
                    "transactions": [
                        _transaction(
                            "tx-2",
                            status="DEFERRED_RELEASED",
                            transaction_type="Refund",
                            amount="-10.00",
                            settlement_id="26960522551",
                        )
                    ]
                }
            },
        ]
    )

    result = sample_finances_transactions(
        client=client,  # type: ignore[arg-type]
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        output_root=tmp_path,
        now=datetime(2026, 8, 9, 12, tzinfo=UTC),
    )

    assert result.pages_fetched == 2
    assert result.transaction_count == 2
    assert client.calls[0]["next_token"] is None
    assert client.calls[1]["next_token"] == "next-1"
    assert client.calls[0]["posted_after"] == datetime(2026, 7, 1, tzinfo=UTC)
    assert client.calls[0]["posted_before"] == datetime(2026, 8, 1, tzinfo=UTC)
    assert (result.output_dir / "pages/page_001.json").exists()
    assert (result.output_dir / "pages/page_002.json").exists()
    combined = json.loads(result.combined_path.read_text())
    assert len(combined["transactions"]) == 2
    assert result.summary["settlement_ids"] == ["26834303761", "26960522551"]
    assert result.summary["total_amounts_by_currency"] == {"USD": "15.00"}
    assert result.summary["breakdown_leaf_totals"]["transaction:Sales/Principal|USD"] == "15.00"
    assert result.summary["breakdown_leaf_totals"]["item:FBAFee|USD"] == "-8.10"


def test_sample_finances_transactions_clamps_recent_posted_before(tmp_path: Path) -> None:
    client = FakeFinancesClient([{"payload": {"transactions": []}}])

    result = sample_finances_transactions(
        client=client,  # type: ignore[arg-type]
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 8, 9),
        end_date=date(2026, 8, 9),
        output_root=tmp_path,
        now=datetime(2026, 8, 9, 12, tzinfo=UTC),
    )

    assert result.summary["posted_before_was_clamped"] is True
    assert client.calls[0]["posted_before"] == datetime(2026, 8, 9, 11, 57, 55, tzinfo=UTC)


def test_sample_finances_transactions_fails_when_pagination_exceeds_bound(tmp_path: Path) -> None:
    client = FakeFinancesClient(
        [{"payload": {"transactions": [], "nextToken": "still-more"}}]
    )

    with pytest.raises(RuntimeError, match="max_pages=1"):
        sample_finances_transactions(
            client=client,  # type: ignore[arg-type]
            marketplace_id="ATVPDKIKX0DER",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            output_root=tmp_path,
            max_pages=1,
            now=datetime(2026, 8, 9, 12, tzinfo=UTC),
        )


def test_summarize_finances_transactions_surfaces_duplicate_ids_and_schema() -> None:
    transaction = _transaction(
        "tx-1",
        status="DEFERRED",
        transaction_type="Shipment",
        amount="25.00",
        settlement_id="27207351391",
    )

    summary = summarize_finances_transactions(
        [transaction, transaction],
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        pages_fetched=1,
        transaction_status_filter=None,
    )

    assert summary["transaction_count"] == 2
    assert summary["unique_transaction_id_count"] == 1
    assert summary["duplicate_transaction_ids"] == {"tx-1": 2}
    assert summary["status_counts"] == {"DEFERRED": 2}
    assert "breakdowns" in summary["observed_transaction_keys"]
    assert summary["observed_context_types"] == ["ProductContext"]
    assert summary["observed_breakdown_types"] == ["FBAFee", "Principal", "Sales"]

    compact = compact_finances_summary(summary, top_breakdowns=1)
    assert len(compact["top_breakdown_leaf_totals"]) == 1


def test_sample_finances_transactions_rejects_more_than_180_days(tmp_path: Path) -> None:
    client = FakeFinancesClient([])

    with pytest.raises(ValueError, match="cannot exceed 180 days"):
        sample_finances_transactions(
            client=client,  # type: ignore[arg-type]
            marketplace_id="ATVPDKIKX0DER",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 31),
            output_root=tmp_path,
            now=datetime(2026, 8, 9, 12, tzinfo=UTC),
        )
