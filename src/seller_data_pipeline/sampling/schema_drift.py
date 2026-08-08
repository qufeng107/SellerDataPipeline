from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from seller_data_pipeline.sampling.ads_report_sampling_plan import get_ads_sampling_plan
from seller_data_pipeline.sampling.report_analyzer import FieldAnalysis, ReportAnalysis

EMPTY_JSON_MARKER_FIELDS = {"[]", "rows[]", "data[]", "reports[]", "records[]", "results[]"}

# Only incompatible changes should block normalized ingestion. Additive/unknown fields remain
# observable through schema-validation events but are intentionally non-blocking.
BLOCKING_SCHEMA_STATUSES = frozenset(
    {
        "missing_fields",
        "schema_drift",
        "validation_failed",
        "empty_report_unexpected",
    }
)


@dataclass(frozen=True)
class ExpectedReportSchema:
    """Expected raw report field shape used before parser/repository upsert.

    This is intentionally based on the downloaded raw file shape, not the SQL table shape.
    SQL table changes must still be recorded in docs/database/database_current_schema_spec.md
    and migrations.
    """

    source_system: str
    report_type: str
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...] = ()
    allow_extra_fields: bool = False
    allow_empty_report: bool = True
    notes: str = ""

    def normalized_expected_fields(self) -> set[str]:
        return {normalize_field_name(field) for field in self.expected_fields}

    def normalized_required_fields(self) -> set[str]:
        fields = self.required_fields or self.expected_fields
        return {normalize_field_name(field) for field in fields}


@dataclass(frozen=True)
class SchemaValidationResult:
    source_system: str
    report_type: str
    marketplace_id: str | None
    raw_file_path: str
    status: str
    severity: str
    row_count: int
    observed_fields: tuple[str, ...]
    expected_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    new_fields: tuple[str, ...]
    unmapped_fields: tuple[str, ...]
    message: str

    @property
    def requires_review(self) -> bool:
        """Return whether ingestion must stop for manual review.

        Warnings are deliberately not equivalent to blocking conditions. In particular,
        additive schema drift (``new_fields``) and unmapped extra fields are safe to
        observe while continuing to parse/write the fields the pipeline already knows.
        """

        return self.status in BLOCKING_SCHEMA_STATUSES or self.severity == "error"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_ads_expected_schema(report_type_id: str) -> ExpectedReportSchema | None:
    """Return expected raw columns for an Amazon Ads reportTypeId from the sampling plan."""

    for item in get_ads_sampling_plan():
        if item.report_type_id == report_type_id:
            return ExpectedReportSchema(
                source_system="amazon_ads",
                report_type=report_type_id,
                expected_fields=tuple(item.columns),
                required_fields=tuple(item.columns),
                allow_extra_fields=False,
                allow_empty_report=True,
                notes=item.purpose,
            )
    return None


def validate_report_schema(
    *,
    analysis: ReportAnalysis,
    expected_schema: ExpectedReportSchema | None = None,
    fail_on_unmapped_fields: bool = False,
) -> SchemaValidationResult:
    """Compare observed raw report fields with expected raw fields.

    Empty downloaded reports are treated as a distinct status. This lets us keep the raw file and
    avoid designing a table from no rows, while still proving that the API/report request worked.
    """

    expected_schema = expected_schema or _default_expected_schema_for_analysis(analysis)
    observed_fields = _observed_normalized_fields(analysis.fields)
    unmapped_fields = tuple(
        sorted(
            normalize_field_name(field.source_field_name)
            for field in analysis.fields
            if normalize_field_name(field.source_field_name) not in EMPTY_JSON_MARKER_FIELDS
            and field.mapping_status != "mapped_candidate"
            and (field.non_empty_count > 0 or analysis.row_count > 0)
        )
    )

    if expected_schema is None:
        status = "no_expected_schema"
        severity = "info"
        message = "No expected raw schema is registered yet; preserve raw file and review manually."
        if fail_on_unmapped_fields and unmapped_fields:
            status = "unmapped_fields"
            severity = "warning"
            message = "No expected schema is registered and some observed fields are unmapped."
        return SchemaValidationResult(
            source_system=analysis.source_system,
            report_type=analysis.report_type,
            marketplace_id=analysis.marketplace_id,
            raw_file_path=analysis.raw_file_path,
            status=status,
            severity=severity,
            row_count=analysis.row_count,
            observed_fields=tuple(sorted(observed_fields)),
            expected_fields=(),
            missing_fields=(),
            new_fields=(),
            unmapped_fields=unmapped_fields,
            message=message,
        )

    expected_fields = expected_schema.normalized_expected_fields()
    required_fields = expected_schema.normalized_required_fields()
    missing_fields = tuple(sorted(required_fields - observed_fields))
    optional_missing_fields = tuple(sorted((expected_fields - required_fields) - observed_fields))
    new_fields = tuple(sorted(observed_fields - expected_fields))
    if expected_schema.allow_extra_fields:
        new_fields = ()

    if analysis.row_count == 0:
        status = "empty_report" if expected_schema.allow_empty_report else "empty_report_unexpected"
        severity = "info" if expected_schema.allow_empty_report else "error"
        message = (
            "Downloaded report is empty. Keep the raw file and do not infer table columns from "
            "this sample alone."
        )
    elif missing_fields and new_fields:
        status = "schema_drift"
        severity = "error"
        message = (
            "Observed report is missing required fields and also contains new fields; "
            "the required data contract is not satisfied."
        )
    elif missing_fields:
        status = "missing_fields"
        severity = "error"
        message = "Observed report is missing one or more required fields."
    elif new_fields:
        status = "new_fields"
        severity = "warning"
        message = (
            "Observed report contains fields that are not in the expected schema; "
            "the required data contract is still satisfied."
        )
        if optional_missing_fields:
            message += " Some known optional fields are absent."
    elif fail_on_unmapped_fields and unmapped_fields:
        status = "unmapped_fields"
        severity = "warning"
        message = (
            "Observed report fields satisfy the required schema but include unmapped fields; "
            "ingestion may continue while the drift is recorded."
        )
    else:
        status = "ok"
        severity = "info"
        if optional_missing_fields:
            message = (
                "Observed report satisfies the required schema; some known optional fields "
                "are absent."
            )
        else:
            message = "Observed report fields match the expected schema."

    return SchemaValidationResult(
        source_system=analysis.source_system,
        report_type=analysis.report_type,
        marketplace_id=analysis.marketplace_id,
        raw_file_path=analysis.raw_file_path,
        status=status,
        severity=severity,
        row_count=analysis.row_count,
        observed_fields=tuple(sorted(observed_fields)),
        expected_fields=tuple(sorted(expected_fields)),
        missing_fields=missing_fields,
        new_fields=new_fields,
        unmapped_fields=unmapped_fields,
        message=message,
    )


def render_schema_validation_markdown(result: SchemaValidationResult) -> str:
    lines = [
        f"# {result.report_type} schema validation",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| source_system | `{result.source_system}` |",
        f"| report_type | `{result.report_type}` |",
        f"| marketplace_id | `{result.marketplace_id or 'unknown'}` |",
        f"| raw_file_path | `{result.raw_file_path}` |",
        f"| row_count | `{result.row_count}` |",
        f"| status | `{result.status}` |",
        f"| severity | `{result.severity}` |",
        f"| message | {result.message} |",
        "",
        "## Observed fields",
        "",
        _render_inline_code_list(result.observed_fields),
        "",
        "## Expected fields",
        "",
        _render_inline_code_list(result.expected_fields),
        "",
        "## Differences",
        "",
        f"- Missing expected fields: {_render_inline_code_list(result.missing_fields)}",
        f"- New/unexpected fields: {_render_inline_code_list(result.new_fields)}",
        f"- Unmapped fields: {_render_inline_code_list(result.unmapped_fields)}",
        "",
    ]
    return "\n".join(lines)


def write_schema_validation_json(path: str | Path, result: SchemaValidationResult) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def normalize_field_name(field_name: str) -> str:
    """Normalize a raw analyzer field path to the row-level field name when possible."""

    name = field_name.strip()
    if name in EMPTY_JSON_MARKER_FIELDS:
        return name
    for prefix in ("[].", "rows[].", "data[].", "reports[].", "records[].", "results[]."):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _default_expected_schema_for_analysis(analysis: ReportAnalysis) -> ExpectedReportSchema | None:
    if analysis.source_system == "amazon_ads":
        return build_ads_expected_schema(analysis.report_type)
    return None


def _observed_normalized_fields(fields: Iterable[FieldAnalysis]) -> set[str]:
    normalized: set[str] = set()
    for field in fields:
        name = normalize_field_name(field.source_field_name)
        if name in EMPTY_JSON_MARKER_FIELDS:
            continue
        normalized.add(name)
    return normalized


def _render_inline_code_list(values: tuple[str, ...]) -> str:
    if not values:
        return "-"
    return ", ".join(f"`{value}`" for value in values)
