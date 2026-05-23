from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Protocol

SUPPORTED_REPORT_TYPES = {
    "monthly_financial_close",
    "weekly_business_review",
    "weekly_ads_optimization",
}

AUDIENCES = {"internal", "operations", "shareholders", "accountant", "ads_operator"}


@dataclass(frozen=True)
class EmailDraft:
    subject: str
    body_html: str
    body_text: str
    template: str


class ReportDeliveryTemplate(Protocol):
    report_type: str

    def render(self, report: dict[str, Any], *, audience: str) -> EmailDraft: ...


def get_template(report_type: str) -> ReportDeliveryTemplate:
    if report_type == "monthly_financial_close":
        return MonthlyFinancialCloseEmailTemplate()
    if report_type == "weekly_business_review":
        return WeeklyBusinessReviewEmailTemplate()
    if report_type == "weekly_ads_optimization":
        return WeeklyAdsOptimizationEmailTemplate()
    supported = ", ".join(sorted(SUPPORTED_REPORT_TYPES))
    raise ValueError(f"Unsupported report_type: {report_type}. Supported: {supported}.")


class MonthlyFinancialCloseEmailTemplate:
    report_type = "monthly_financial_close"

    def render(self, report: dict[str, Any], *, audience: str) -> EmailDraft:
        marketplace_id = _text(report.get("marketplace_id"), "-")
        status = _status_label(report)
        currency = _currency(report)
        period = report.get("period") or {}
        month = _text(period.get("month"), _period_key(report))
        summary = report.get("financial_summary") or {}
        executive = report.get("executive_summary") or {}
        profit = _money(summary.get("estimated_operating_profit"), currency)
        subject = f"[Monthly Close] Amazon US {month} | Profit {profit} | Status {status}"
        rows = [
            ("Settlement net amount", _money(summary.get("settlement_net_amount"), currency)),
            ("Product sales amount", _money(summary.get("product_sales_amount"), currency)),
            ("Product sales units", _text(summary.get("product_sales_units"), "0")),
            ("Internal COGS", _money(summary.get("internal_cogs"), currency)),
            ("Estimated operating profit", profit),
            ("Profit margin", _percent(summary.get("profit_margin"))),
            ("Advertising cost", _money(summary.get("advertising_cost"), currency)),
            ("FBA fee", _money(summary.get("fba_fee"), currency)),
            ("Refund", _money(summary.get("refund"), currency)),
            ("Promotion cost", _money(summary.get("promotion_cost"), currency)),
            ("Reimbursement", _money(summary.get("reimbursement"), currency)),
        ]
        key_points = _as_text_list(executive.get("key_points"))
        headline = _text(executive.get("headline"), "Monthly financial close report is ready.")
        intro = (
            f"Monthly Financial Close for {month} ({marketplace_id}) is ready. "
            "Settlement is the financial source of truth; operational data is context only."
        )
        return _build_draft(
            template=self.report_type,
            subject=subject,
            title=f"Monthly Financial Close — {month}",
            status=status,
            audience=audience,
            intro=intro,
            headline=headline,
            metric_rows=rows,
            key_points=key_points,
            action_note=(
                "Please review the attached XLSX workbook, especially Summary, SKU Profit "
                "and Reconciliation Checks."
            ),
        )


class WeeklyBusinessReviewEmailTemplate:
    report_type = "weekly_business_review"

    def render(self, report: dict[str, Any], *, audience: str) -> EmailDraft:
        marketplace_id = _text(report.get("marketplace_id"), "-")
        profile_id = _text(report.get("profile_id"), "-")
        status = _status_label(report)
        currency = _currency(report)
        period_key = _period_key(report)
        sales_summary = report.get("sales_traffic_summary") or {}
        ads_summary = (report.get("ads_overview") or {}).get("summary") or {}
        executive = report.get("executive_summary") or {}
        sales = _money(sales_summary.get("ordered_product_sales"), currency)
        subject = f"[Weekly Business Review] Amazon US {period_key} | Sales {sales} | Status {status}"
        rows = [
            ("Ordered product sales", sales),
            ("Units ordered", _text(sales_summary.get("units_ordered"), "0")),
            ("Sessions", _text(sales_summary.get("sessions"), "0")),
            ("Unit session rate", _percent(sales_summary.get("unit_session_percentage"))),
            ("Ads spend", _money(ads_summary.get("ads_spend"), currency)),
            ("Ads sales 7d", _money(ads_summary.get("ads_sales_7d"), currency)),
            ("ACOS", _percent(ads_summary.get("acos"))),
            ("TACOS", _percent(ads_summary.get("tacos"))),
            ("Estimated COGS", _kpi_value(report, "estimated_cogs", currency)),
            ("Contribution after ads", _kpi_value(report, "contribution_after_ads", currency)),
            ("Alerts", _text(len(report.get("alerts") or []), "0")),
        ]
        headline = _text(executive.get("headline"), "Weekly business review is ready.")
        key_points = _as_text_list(executive.get("key_points"))
        intro = (
            f"Weekly Business Review for {period_key} ({marketplace_id}, profile {profile_id}) "
            "is ready. This is an operational report; Settlement is finance context only."
        )
        return _build_draft(
            template=self.report_type,
            subject=subject,
            title=f"Weekly Business Review — {period_key}",
            status=status,
            audience=audience,
            intro=intro,
            headline=headline,
            metric_rows=rows,
            key_points=key_points,
            action_note=(
                "Please review the attached XLSX workbook, especially Daily Trend, SKU "
                "Performance, Inventory Risk and Alerts/Actions."
            ),
        )


class WeeklyAdsOptimizationEmailTemplate:
    report_type = "weekly_ads_optimization"

    def render(self, report: dict[str, Any], *, audience: str) -> EmailDraft:
        marketplace_id = _text(report.get("marketplace_id"), "-")
        profile_id = _text(report.get("profile_id"), "-")
        status = _status_label(report)
        currency = _currency(report)
        period_key = _period_key(report)
        overall = report.get("overall_summary") or {}
        actions = report.get("action_items") or []
        search_actions = report.get("search_term_action_candidates") or []
        spend = _money(overall.get("ads_spend"), currency)
        acos = _percent(overall.get("acos"))
        subject = f"[Ads Optimization] Amazon US {period_key} | ACOS {acos} | Actions {len(actions)}"
        rows = [
            ("Ads spend", spend),
            ("Ads sales 7d", _money(overall.get("ads_sales_7d"), currency)),
            ("Purchases 7d", _text(overall.get("ads_purchases_7d"), "0")),
            ("Clicks", _text(overall.get("clicks"), "0")),
            ("Impressions", _text(overall.get("impressions"), "0")),
            ("ACOS", acos),
            ("ROAS", _ratio_number(overall.get("roas"))),
            ("TACOS", _percent(overall.get("tacos"))),
            ("Search term actions", _text(len(search_actions), "0")),
            ("Action items", _text(len(actions), "0")),
        ]
        executive = report.get("executive_summary") or {}
        headline = _text(executive.get("headline"), "Weekly ads optimization report is ready.")
        key_points = _as_text_list(executive.get("key_points"))
        top_actions = _format_top_action_points(actions)
        intro = (
            f"Weekly Ads Optimization report for {period_key} ({marketplace_id}, profile "
            f"{profile_id}) is ready. This report is for manual optimization decisions only."
        )
        return _build_draft(
            template=self.report_type,
            subject=subject,
            title=f"Weekly Ads Optimization — {period_key}",
            status=status,
            audience=audience,
            intro=intro,
            headline=headline,
            metric_rows=rows,
            key_points=key_points + top_actions,
            action_note=(
                "Do not auto-apply these suggestions. Review relevance, inventory, current "
                "bids, budgets and existing negatives in Amazon Ads Console first."
            ),
        )


def _build_draft(
    *,
    template: str,
    subject: str,
    title: str,
    status: str,
    audience: str,
    intro: str,
    headline: str,
    metric_rows: list[tuple[str, str]],
    key_points: list[str],
    action_note: str,
) -> EmailDraft:
    html_rows = "".join(
        "<tr>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;'><strong>{escape(label)}</strong></td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;'>{escape(value)}</td>"
        "</tr>"
        for label, value in metric_rows
    )
    html_points = "".join(f"<li>{escape(point)}</li>" for point in key_points[:12])
    body_html = f"""<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.45;">
    <h2>{escape(title)}</h2>
    <p><strong>Status:</strong> {escape(status)} &nbsp; <strong>Audience:</strong> {escape(audience)}</p>
    <p>{escape(intro)}</p>
    <p><strong>Headline:</strong> {escape(headline)}</p>
    <h3>Key metrics</h3>
    <table style="border-collapse: collapse; min-width: 520px;">{html_rows}</table>
    <h3>Key points</h3>
    <ul>{html_points}</ul>
    <h3>Attachment</h3>
    <p>The attached XLSX workbook contains the detailed report sheets for manual review.</p>
    <p><strong>Note:</strong> {escape(action_note)}</p>
  </body>
</html>
"""
    text_lines = [
        title,
        f"Status: {status}",
        f"Audience: {audience}",
        "",
        intro,
        "",
        f"Headline: {headline}",
        "",
        "Key metrics:",
    ]
    text_lines.extend(f"- {label}: {value}" for label, value in metric_rows)
    text_lines.extend(["", "Key points:"])
    text_lines.extend(f"- {point}" for point in key_points[:12])
    text_lines.extend(
        [
            "",
            "Attachment: the XLSX workbook contains the detailed report sheets for manual review.",
            f"Note: {action_note}",
            "",
        ]
    )
    return EmailDraft(
        subject=subject.strip(),
        body_html=body_html,
        body_text="\n".join(text_lines),
        template=template,
    )


def _period_key(report: dict[str, Any]) -> str:
    period = report.get("period") or {}
    if period.get("month"):
        return str(period["month"])
    if period.get("week_start") and period.get("week_end"):
        return f"{period['week_start']}_{period['week_end']}"
    if period.get("start_date") and period.get("end_date"):
        return f"{period['start_date']}_{period['end_date']}"
    return "unknown_period"


def _status_label(report: dict[str, Any]) -> str:
    return _text(report.get("status"), "unknown").upper()


def _currency(report: dict[str, Any]) -> str:
    value = report.get("currency")
    if isinstance(value, str) and value.strip():
        return value.strip().upper()
    return "USD"


def _money(value: Any, currency: str) -> str:
    text = _text(value, "0.00")
    try:
        amount = float(text)
        return f"{currency} {amount:,.2f}"
    except ValueError:
        return f"{currency} {text}"


def _percent(value: Any) -> str:
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return _text(value, "-")


def _ratio_number(value: Any) -> str:
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return _text(value, "-")


def _text(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value if value else default
    return str(value)


def _as_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item, "") for item in value if _text(item, "").strip()]


def _kpi_value(report: dict[str, Any], metric: str, currency: str) -> str:
    for row in report.get("kpi_summary") or []:
        if isinstance(row, dict) and row.get("metric") == metric:
            value = row.get("current_value")
            if row.get("unit"):
                return _money(value, currency)
            return _text(value, "-")
    return "-"


def _format_top_action_points(actions: Any) -> list[str]:
    if not isinstance(actions, list):
        return []
    points: list[str] = []
    for item in actions[:5]:
        if not isinstance(item, dict):
            continue
        priority = _text(item.get("priority"), "-")
        action_type = _text(item.get("action_type"), "-")
        entity = _text(item.get("entity_text"), _text(item.get("entity_id"), "-"))
        reason = _text(item.get("reason"), "")
        points.append(f"Action candidate ({priority}): {action_type} — {entity}. {reason}")
    return points
