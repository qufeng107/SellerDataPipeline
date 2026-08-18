from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Protocol

from seller_data_pipeline.services.report_bilingual import (
    ACTION_ZH,
    PRIORITY_ZH,
    REASON_ZH,
)

SUPPORTED_REPORT_TYPES = {
    "monthly_financial_close",
    "weekly_business_review",
    "weekly_ads_optimization",
}

AUDIENCES = {"internal", "operations", "shareholders", "accountant", "ads_operator"}

METRIC_LABEL_ZH = {
    "Settlement net amount": "Settlement净额",
    "Product sales amount": "商品销售额",
    "Product sales units": "商品销售件数",
    "Costed units": "成本计量件数（销售+清算）",
    "Warehouse-lost inventory units": "仓库丢失库存件数",
    "Warehouse-lost inventory write-off": "仓库丢失库存成本核销",
    "Internal COGS": "内部COGS",
    "Product cost COGS": "商品货款COGS",
    "First-mile freight COGS": "头程海运COGS",
    "Total landed COGS": "到岸COGS合计",
    "Management operating profit": "经营利润",
    "Management operating margin": "经营利润率",
    "Settlement close profit": "Settlement结算口径利润",
    "Estimated operating profit": "估算经营利润",
    "Profit margin": "利润率",
    "Advertising cost": "广告费用",
    "FBA fee": "FBA费用",
    "Refund": "退款",
    "Promotion cost": "促销成本",
    "Reimbursement": "赔偿",
    "Ordered product sales": "订购商品销售额",
    "Units ordered": "订购件数",
    "Sessions": "会话数",
    "Unit session rate": "单位会话率",
    "Ads spend": "广告花费",
    "Ads sales 7d": "7天归因广告销售额",
    "Purchases 7d": "7天归因订单数",
    "Clicks": "点击量",
    "Impressions": "曝光量",
    "ACOS": "ACOS广告销售成本比",
    "ROAS": "ROAS广告投入产出比",
    "TACOS": "TACOS总广告成本比",
    "Estimated COGS": "估算COGS",
    "Contribution after ads": "扣广告后贡献利润",
    (
        "Contribution after COGS & Ads (before full Amazon fees)"
    ): "广告和货本后贡献（未扣完整Amazon费用）",
    "Search term actions": "搜索词动作数",
    "Action items": "动作候选数",
    "Active action items": "当前启用广告动作数",
    "Historical/paused lessons": "历史/暂停广告复盘项",
    "Alerts": "告警数量",
}


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
        natural = report.get("natural_month_finance") or {}
        executive = report.get("executive_summary") or {}
        operating_profit_value = (
            summary.get("management_operating_profit")
            or summary.get("management_estimated_profit_report_date_ads")
            or summary.get("estimated_operating_profit")
        )
        operating_margin_value = (
            summary.get("management_operating_margin")
            or summary.get("management_profit_margin_report_date_ads")
            or summary.get("profit_margin")
        )
        landed_cogs_value = (
            natural.get("landed_cogs")
            or summary.get("landed_cogs")
            or summary.get("internal_cogs")
        )
        product_sales_value = natural.get("product_sales_amount") or summary.get("product_sales_amount")
        product_sales_units_value = natural.get("product_sales_units") or summary.get("product_sales_units")
        costed_units_value = natural.get("costed_units")
        inventory_loss_units_value = natural.get("inventory_loss_units")
        inventory_loss_cost_value = natural.get("inventory_loss_landed_cost")
        product_cost_cogs_value = natural.get("product_cost_cogs") or summary.get("product_cost_cogs")
        first_mile_cogs_value = natural.get("first_mile_cogs") or summary.get("first_mile_cogs")
        profit = _money(operating_profit_value, currency)
        subject = f"[月结 Monthly Close] Amazon US {month} | 经营利润 Operating Profit {profit} | 数据状态 Data Status {status}"
        rows = [
            ("Product sales amount", _money(product_sales_value, currency)),
            ("Product sales units", _text(product_sales_units_value, "0")),
            ("Costed units", _text(costed_units_value, "0")),
            ("Warehouse-lost inventory units", _text(inventory_loss_units_value, "0")),
            ("Warehouse-lost inventory write-off", _money(inventory_loss_cost_value, currency)),
            ("Ads spend", _money(summary.get("ads_api_report_date_spend"), currency)),
            ("Product cost COGS", _money(product_cost_cogs_value, currency)),
            ("First-mile freight COGS", _money(first_mile_cogs_value, currency)),
            ("Total landed COGS", _money(landed_cogs_value, currency)),
            ("Management operating profit", profit),
            ("Management operating margin", _percent(operating_margin_value)),
            ("Settlement net amount", _money(summary.get("settlement_net_amount"), currency)),
            (
                "Settlement close profit",
                _money(
                    summary.get("settlement_close_profit")
                    or summary.get("settlement_led_estimated_profit")
                    or summary.get("estimated_operating_profit"),
                    currency,
                ),
            ),
        ]
        key_points = _as_text_list(executive.get("key_points"))
        headline = _text(executive.get("headline"), "Monthly financial close report is ready.")
        headline_zh = f"{month} 月结报表已生成，经营利润为 {profit}，状态 {status}。"
        intro = (
            f"Monthly Financial Close for {month} ({marketplace_id}) is ready. "
            "Management operating profit uses Finances API marketplace-local natural-month "
            "transactions, report-date Ads spend, landed COGS and verified warehouse-lost "
            "inventory write-offs; Settlement remains a "
            "close/cash reconciliation reference."
        )
        intro_zh = (
            f"{month} 月度财务结算报表已生成，市场为 {marketplace_id}。"
            "经营利润采用 Finances API 美国站本地自然月交易、Ads API 月度广告发生口径，"
            "扣除销售/清算到岸COGS，并对已核验的 WAREHOUSE_LOST 仓库丢失库存单独核销成本；"
            "Settlement 继续作为结算、现金与回款对账参考。"
        )
        key_points_zh = [
            f"数据校验状态：{status}（仅表示自动数据与核验规则通过，不代表会计师已完成正式审核）。",
            f"商品销售额：{_money(product_sales_value, currency)}。",
            (
                f"商品销售件数：{_text(product_sales_units_value, '0')}；"
                f"成本计量件数（销售+清算）：{_text(costed_units_value, '0')}；"
                f"仓库丢失库存件数：{_text(inventory_loss_units_value, '0')}。"
            ),
            f"到岸COGS：{_money(landed_cogs_value, currency)}。",
            f"仓库丢失库存成本核销：{_money(inventory_loss_cost_value, currency)}。",
            f"经营利润：{profit}。",
            f"Settlement净额：{_money(summary.get('settlement_net_amount'), currency)}。",
            f"非信息类警告：{_non_info_warning_count(report)}。",
        ]
        return _build_draft(
            template=self.report_type,
            subject=subject,
            title=f"Monthly Financial Close — {month}",
            title_zh=f"月度财务结算报表 — {month}",
            status=status,
            audience=audience,
            intro=intro,
            intro_zh=intro_zh,
            headline=headline,
            headline_zh=headline_zh,
            metric_rows=rows,
            key_points=key_points,
            key_points_zh=key_points_zh,
            action_note=(
                "Please review both XLSX attachments: Monthly Operating Report for management "
                "performance and Accountant Monthly Workbook for bookkeeping support."
            ),
            action_note_zh=(
                "请查看两份 XLSX 附件：月度经营报告用于经营分析；会计月度底稿用于做账辅助与交易追溯。"
                "会计应以会计月度底稿的 posted-date Amazon 交易分类为主，并按需填写 USD/CNY 记账汇率；"
                "经营月报中的 Ads API 当月消耗和 Management Operating Profit 仅作经营分析，不直接替代会计账单。"
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
        subject = f"[周经营 WBR] Amazon US {period_key} | Sales {sales} | Status {status}"
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
            (
                "Contribution after COGS & Ads (before full Amazon fees)",
                _kpi_value(report, "contribution_after_ads", currency),
            ),
            ("Alerts", _text(len(report.get("alerts") or []), "0")),
        ]
        headline = _text(executive.get("headline"), "Weekly business review is ready.")
        key_points = _as_text_list(executive.get("key_points"))
        intro = (
            f"Weekly Business Review for {period_key} ({marketplace_id}, profile {profile_id}) "
            "is ready. This is an operational report; Settlement is finance context only, "
            "and contribution after COGS & Ads is not final net profit."
        )
        intro_zh = (
            f"{period_key} 每周经营复盘已生成，市场为 {marketplace_id}，"
            f"广告 profile 为 {profile_id}。"
            "本报表用于运营复盘，Settlement 仅作财务参考；"
            "广告和货本后贡献不等于最终净利润。"
        )
        key_points_zh = [
            f"报表状态：{status}。",
            f"本周订购销售额：{sales}。",
            f"广告花费：{_money(ads_summary.get('ads_spend'), currency)}。",
            (
                "广告和货本后贡献（未扣完整Amazon费用）："
                f"{_kpi_value(report, 'contribution_after_ads', currency)}。"
            ),
            f"告警数量：{len(report.get('alerts') or [])}。",
        ]
        return _build_draft(
            template=self.report_type,
            subject=subject,
            title=f"Weekly Business Review — {period_key}",
            title_zh=f"每周经营复盘 — {period_key}",
            status=status,
            audience=audience,
            intro=intro,
            intro_zh=intro_zh,
            headline=headline,
            headline_zh=f"{period_key} 周经营报表已生成，本周订购销售额为 {sales}。",
            metric_rows=rows,
            key_points=key_points,
            key_points_zh=key_points_zh,
            action_note=(
                "Please review the attached XLSX workbook, especially Daily Trend, SKU "
                "Performance, Inventory Risk and Alerts/Actions."
            ),
            action_note_zh=(
                "请查看附件 XLSX，重点复核 Daily Trend、SKU Performance、库存风险和行动项。"
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
        actions = report.get("active_action_items") or report.get("action_items") or []
        historical_actions = report.get("historical_action_items") or []
        search_actions = report.get("search_term_action_candidates") or []
        spend = _money(overall.get("ads_spend"), currency)
        acos = _percent(overall.get("acos"))
        subject = (
            f"[广告优化 Ads Optimization] Amazon US {period_key} | ACOS {acos} | "
            f"Active Actions {len(actions)}"
        )
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
            ("Active action items", _text(len(actions), "0")),
            ("Historical/paused lessons", _text(len(historical_actions), "0")),
        ]
        executive = report.get("executive_summary") or {}
        headline = _text(executive.get("headline"), "Weekly ads optimization report is ready.")
        key_points = _as_text_list(executive.get("key_points"))
        top_actions = _format_top_action_points(actions)
        top_actions_zh = _format_top_action_points_zh(actions)
        negative_count = sum(1 for item in search_actions if _is_negative_action(item))
        harvest_count = sum(
            1 for item in search_actions if _action_kind(item) == "harvest_to_exact_candidate"
        )
        intro = (
            f"Weekly Ads Optimization report for {period_key} ({marketplace_id}, profile "
            f"{profile_id}) is ready. This report is for manual optimization decisions only."
        )
        intro_zh = (
            f"{period_key} 每周广告优化报表已生成，市场为 {marketplace_id}，"
            f"广告 profile 为 {profile_id}。本报表只用于人工广告优化决策。"
        )
        key_points_zh = [
            f"报表状态：{status}。",
            f"广告7天归因销售额：{_money(overall.get('ads_sales_7d'), currency)}。",
            f"ROAS：{_ratio_number(overall.get('roas'))}；TACOS：{_percent(overall.get('tacos'))}。",
            f"否词候选：{negative_count}；收词候选：{harvest_count}；当前启用广告动作：{len(actions)}。",
            f"非信息类警告：{_non_info_warning_count(report)}。",
        ]
        return _build_draft(
            template=self.report_type,
            subject=subject,
            title=f"Weekly Ads Optimization — {period_key}",
            title_zh=f"每周广告优化报表 — {period_key}",
            status=status,
            audience=audience,
            intro=intro,
            intro_zh=intro_zh,
            headline=headline,
            headline_zh=(
                f"{period_key} 广告花费为 {spend}，ACOS 为 {acos}，动作候选 {len(actions)} 个。"
            ),
            metric_rows=rows,
            key_points=key_points + top_actions,
            key_points_zh=key_points_zh + top_actions_zh,
            action_note=(
                "Do not auto-apply these suggestions. Review relevance, inventory, current "
                "bids, budgets and existing negatives in Amazon Ads Console first."
            ),
            action_note_zh=(
                "不要自动执行这些建议。请先在 Amazon Ads Console 中复核相关性、库存、"
                "当前竞价、预算和已有否词。"
            ),
        )


def _build_draft(
    *,
    template: str,
    subject: str,
    title: str,
    title_zh: str,
    status: str,
    audience: str,
    intro: str,
    intro_zh: str,
    headline: str,
    headline_zh: str,
    metric_rows: list[tuple[str, str]],
    key_points: list[str],
    key_points_zh: list[str],
    action_note: str,
    action_note_zh: str,
) -> EmailDraft:
    html_rows = "".join(
        "<tr>"
        "<td style='padding:6px 10px;border-bottom:1px solid #eee;'>"
        f"<strong>{escape(_metric_label(label))}</strong></td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;'>{escape(value)}</td>"
        "</tr>"
        for label, value in metric_rows
    )
    html_points_zh = "".join(f"<li>{escape(point)}</li>" for point in key_points_zh[:12])
    html_points = "".join(f"<li>{escape(point)}</li>" for point in key_points[:12])
    body_html = f"""<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.45;">
    <h2>{escape(title_zh)}<br><span style="font-size:16px;color:#555;">{escape(title)}</span></h2>
    <p><strong>状态 Status:</strong> {escape(status)} &nbsp;
       <strong>受众 Audience:</strong> {escape(audience)}</p>
    <p>{escape(intro_zh)}<br><span style="color:#555;">{escape(intro)}</span></p>
    <p><strong>摘要 Headline:</strong> {escape(headline_zh)}<br>
       <span style="color:#555;">{escape(headline)}</span></p>
    <h3>关键指标 Key metrics</h3>
    <table style="border-collapse: collapse; min-width: 520px;">{html_rows}</table>
    <h3>重点说明 Key points</h3>
    <ul>{html_points_zh}</ul>
    <h3>English reference</h3>
    <ul>{html_points}</ul>
    <h3>附件 Attachment</h3>
    <p>附件 XLSX 工作簿包含可人工复核的详细报表。<br>
       The attached XLSX workbook contains the detailed report sheets for manual review.</p>
    <p><strong>注意 Note:</strong> {escape(action_note_zh)}<br>{escape(action_note)}</p>
  </body>
</html>
"""
    text_lines = [
        f"{title_zh} / {title}",
        f"状态 Status: {status}",
        f"受众 Audience: {audience}",
        "",
        intro_zh,
        intro,
        "",
        f"摘要 Headline: {headline_zh}",
        f"English: {headline}",
        "",
        "关键指标 Key metrics:",
    ]
    text_lines.extend(f"- {_metric_label(label)}: {value}" for label, value in metric_rows)
    text_lines.extend(["", "重点说明 Key points:"])
    text_lines.extend(f"- {point}" for point in key_points_zh[:12])
    text_lines.extend(["", "English reference:"])
    text_lines.extend(f"- {point}" for point in key_points[:12])
    text_lines.extend(
        [
            "",
            "附件 Attachment: XLSX 工作簿包含可人工复核的详细报表。",
            "Attachment: the XLSX workbook contains the detailed report sheets for manual review.",
            f"注意 Note: {action_note_zh}",
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


def _metric_label(label: str) -> str:
    zh = METRIC_LABEL_ZH.get(label)
    return f"{zh} / {label}" if zh else label


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


def _format_top_action_points_zh(actions: Any) -> list[str]:
    if not isinstance(actions, list):
        return []
    points: list[str] = []
    for item in actions[:5]:
        if not isinstance(item, dict):
            continue
        priority_text = _text(item.get("priority"), "-")
        action_type_text = _text(item.get("action_type"), "-")
        priority = PRIORITY_ZH.get(priority_text.lower(), priority_text)
        action_type = ACTION_ZH.get(action_type_text, action_type_text)
        entity = _text(item.get("entity_text"), _text(item.get("entity_id"), "-"))
        reason = REASON_ZH.get(_text(item.get("reason"), ""), _text(item.get("reason"), ""))
        points.append(f"动作候选（{priority}）：{action_type} — {entity}。{reason}")
    return points


def _is_negative_action(item: Any) -> bool:
    return "negative" in _action_kind(item)


def _action_kind(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return _text(item.get("action_label", item.get("action_type")), "")


def _non_info_warning_count(report: dict[str, Any]) -> int:
    return len([w for w in report.get("warnings") or [] if w.get("severity") != "info"])


__all__ = [
    "AUDIENCES",
    "EmailDraft",
    "ReportDeliveryTemplate",
    "SUPPORTED_REPORT_TYPES",
    "get_template",
]
