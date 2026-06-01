from __future__ import annotations

from seller_data_pipeline.services.report_delivery_templates import get_template


def test_monthly_template_renders_core_metrics() -> None:
    report = {
        "report_type": "monthly_financial_close",
        "status": "ok",
        "currency": "USD",
        "marketplace_id": "ATVPDKIKX0DER",
        "period": {"month": "2026-04"},
        "financial_summary": {
            "settlement_net_amount": "1853.15",
            "product_sales_amount": "6241.84",
            "product_sales_units": 258,
            "internal_cogs": "1075.86",
            "estimated_operating_profit": "777.29",
            "profit_margin": "0.1245",
            "advertising_cost": "-2003.85",
            "fba_fee": "-1135.83",
            "refund": "-537.65",
            "promotion_cost": "-315.27",
            "reimbursement": "101.28",
        },
        "executive_summary": {"headline": "2026-04 estimated operating profit was USD 777.29."},
    }

    draft = get_template("monthly_financial_close").render(report, audience="shareholders")

    assert "[月结 Monthly Close]" in draft.subject
    assert "Profit USD 777.29" in draft.subject
    assert "Settlement净额 / Settlement net amount" in draft.body_text
    assert "USD 1,853.15" in draft.body_html


def test_weekly_business_template_renders_core_metrics() -> None:
    report = {
        "report_type": "weekly_business_review",
        "status": "ok",
        "currency": "USD",
        "marketplace_id": "ATVPDKIKX0DER",
        "profile_id": "3917953989967300",
        "period": {"week_start": "2026-05-11", "week_end": "2026-05-17"},
        "sales_traffic_summary": {
            "ordered_product_sales": "602.38",
            "units_ordered": 24,
            "sessions": 501,
            "unit_session_percentage": "0.0479",
        },
        "ads_overview": {
            "summary": {
                "ads_spend": "105.01",
                "ads_sales_7d": "276.00",
                "acos": "0.3805",
                "tacos": "0.1743",
            }
        },
        "kpi_summary": [
            {"metric": "estimated_cogs", "current_value": "100.08", "unit": "USD"},
            {"metric": "contribution_after_ads", "current_value": "397.29", "unit": "USD"},
        ],
        "alerts": [{"alert_type": "watch"}],
    }

    draft = get_template("weekly_business_review").render(report, audience="operations")

    assert "[周经营 WBR]" in draft.subject
    assert "Sales USD 602.38" in draft.subject
    expected_label = (
        "广告和货本后贡献（未扣完整Amazon费用） / "
        "Contribution after COGS & Ads (before full Amazon fees)"
    )
    assert expected_label in draft.body_text
    assert "17.43%" in draft.body_html


def test_weekly_ads_template_renders_action_counts() -> None:
    report = {
        "report_type": "weekly_ads_optimization",
        "status": "ok",
        "currency": "USD",
        "marketplace_id": "ATVPDKIKX0DER",
        "profile_id": "3917953989967300",
        "period": {"week_start": "2026-05-11", "week_end": "2026-05-17"},
        "overall_summary": {
            "ads_spend": "105.01",
            "ads_sales_7d": "276.00",
            "ads_purchases_7d": 10,
            "clicks": 242,
            "impressions": 81167,
            "acos": "0.3805",
            "roas": "2.63",
            "tacos": "0.1743",
        },
        "search_term_action_candidates": [{"search_term": "passport holder"}],
        "active_action_items": [
            {
                "priority": "high",
                "action_type": "negative_candidate",
                "entity_text": "passport holder",
                "reason": "Spent with no sales.",
            }
        ],
    }

    draft = get_template("weekly_ads_optimization").render(report, audience="ads_operator")

    assert "[广告优化 Ads Optimization]" in draft.subject
    assert "ACOS 38.05%" in draft.subject
    assert "动作候选" in draft.body_text
    assert "不要自动执行" in draft.body_html
