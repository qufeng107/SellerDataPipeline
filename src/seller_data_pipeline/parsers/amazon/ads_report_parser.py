from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.raw_report_files import decode_report_content


@dataclass(frozen=True)
class AdsReportRecord:
    """Generic normalized row for Amazon Ads Reporting v3 raw JSON samples."""

    profile_id: str
    report_type_id: str
    report_date: str | None
    campaign_id: str | None
    campaign_name: str | None
    campaign_status: str | None
    ad_group_id: str | None
    ad_group_name: str | None
    keyword_id: str | None
    keyword: str | None
    match_type: str | None
    targeting: str | None
    search_term: str | None
    advertised_asin: str | None
    advertised_sku: str | None
    purchased_asin: str | None
    impressions: int | None
    clicks: int | None
    cost: Decimal | None
    sales_7d: Decimal | None
    purchases_7d: int | None
    units_sold_clicks_7d: int | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_index: int
    source_row_hash: str
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = str(value)
        return payload


class AdsReportParser:
    """Parser for Amazon Ads Reporting v3 GZIP_JSON downloads.

    The first parser is intentionally generic because the project is still sampling real Ads
    report shapes. It normalizes common Sponsored Products fields while preserving the full raw
    row in raw_data so later repository-specific parsers can be derived safely from samples.
    """

    def parse_file(
        self,
        *,
        raw_file_path: str | Path,
        profile_id: str,
        report_type_id: str,
        source_report_id: str | None = None,
    ) -> list[AdsReportRecord]:
        path = Path(raw_file_path)
        text, _encoding = decode_report_content(path.read_bytes())
        return self.parse_text(
            text=text,
            profile_id=profile_id,
            report_type_id=report_type_id,
            source_report_id=source_report_id,
            source_raw_file_path=str(path),
        )

    def parse(self, content: str) -> list[dict[str, Any]]:
        """Backward-compatible entrypoint used by older tests/callers."""

        return [
            record.to_dict()
            for record in self.parse_text(
                text=content,
                profile_id="UNKNOWN",
                report_type_id="UNKNOWN",
            )
        ]

    def parse_text(
        self,
        *,
        text: str,
        profile_id: str,
        report_type_id: str,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> list[AdsReportRecord]:
        payload = json.loads(text)
        rows = _extract_rows(payload)
        records: list[AdsReportRecord] = []
        for index, row in enumerate(rows, start=1):
            records.append(
                AdsReportRecord(
                    profile_id=str(profile_id),
                    report_type_id=str(report_type_id),
                    report_date=_empty_to_none(row.get("date")),
                    campaign_id=_string_id(row.get("campaignId")),
                    campaign_name=_empty_to_none(row.get("campaignName")),
                    campaign_status=_empty_to_none(row.get("campaignStatus")),
                    ad_group_id=_string_id(row.get("adGroupId")),
                    ad_group_name=_empty_to_none(row.get("adGroupName")),
                    keyword_id=_string_id(row.get("keywordId")),
                    keyword=_empty_to_none(row.get("keyword")),
                    match_type=_empty_to_none(row.get("matchType")),
                    targeting=_empty_to_none(row.get("targeting")),
                    search_term=_empty_to_none(row.get("searchTerm")),
                    advertised_asin=_empty_to_none(row.get("advertisedAsin")),
                    advertised_sku=_empty_to_none(row.get("advertisedSku")),
                    purchased_asin=_empty_to_none(row.get("purchasedAsin")),
                    impressions=_parse_int(row.get("impressions")),
                    clicks=_parse_int(row.get("clicks")),
                    cost=_parse_decimal(row.get("cost")),
                    sales_7d=_parse_decimal(row.get("sales7d")),
                    purchases_7d=_parse_int(row.get("purchases7d")),
                    units_sold_clicks_7d=_parse_int(row.get("unitsSoldClicks7d")),
                    source_system="amazon_ads",
                    source_report_type=str(report_type_id),
                    source_report_id=source_report_id,
                    source_raw_file_path=source_raw_file_path,
                    source_row_index=index,
                    source_row_hash=compute_source_row_hash(
                        profile_id=str(profile_id),
                        report_type_id=str(report_type_id),
                        row_index=index,
                        row=row,
                    ),
                    raw_data=row,
                )
            )
        return records


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_as_dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("reports", "rows", "data", "records", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [_as_dict(item) for item in value if isinstance(item, dict)]
        # Some small diagnostic payloads are a single object. Treat it as one row only if it
        # contains campaign/report-like scalar fields.
        if any(key in payload for key in ("campaignId", "impressions", "clicks", "cost")):
            return [_as_dict(payload)]
    raise ValueError("Amazon Ads report JSON must be a list of row objects or contain rows/data")


def compute_source_row_hash(
    *,
    profile_id: str,
    report_type_id: str,
    row_index: int,
    row: dict[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "profile_id": profile_id,
            "report_type_id": report_type_id,
            "row_index": row_index,
            "row": row,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _empty_to_none(value: Any) -> str | None:
    value = "" if value is None else str(value).strip()
    return value or None


def _string_id(value: Any) -> str | None:
    value = _empty_to_none(value)
    if value is None:
        return None
    return value


def _parse_int(value: Any) -> int | None:
    value = _empty_to_none(value)
    if value is None:
        return None
    return int(Decimal(value))


def _parse_decimal(value: Any) -> Decimal | None:
    value = _empty_to_none(value)
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc
