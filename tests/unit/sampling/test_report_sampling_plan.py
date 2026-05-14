from __future__ import annotations

from seller_data_pipeline.integrations.amazon import report_types as rt
from seller_data_pipeline.sampling.report_sampling_plan import get_sampling_plan


def test_sampling_plan_excludes_sensitive_reports_by_default() -> None:
    items = get_sampling_plan()

    assert items
    assert all(not item.sensitive for item in items)
    assert rt.SETTLEMENT_V2 in {item.report_type for item in items}
    assert rt.FBA_FULFILLED_SHIPMENTS not in {item.report_type for item in items}


def test_sampling_plan_can_include_sensitive_reports() -> None:
    items = get_sampling_plan(include_sensitive=True)

    report_types = {item.report_type for item in items}
    assert rt.FBA_CUSTOMER_RETURNS in report_types
    assert rt.FBA_FULFILLED_SHIPMENTS in report_types


def test_sampling_plan_is_priority_sorted() -> None:
    priorities = [item.priority for item in get_sampling_plan(include_sensitive=True)]

    assert priorities == sorted(priorities)


def test_promotion_and_coupon_sampling_plan_include_required_date_options() -> None:
    items = {item.report_type: item for item in get_sampling_plan()}

    assert items[rt.PROMOTION_PERFORMANCE].days == 89
    assert items[rt.PROMOTION_PERFORMANCE].report_options == {
        "promotionStartDateFrom": "{data_start_time}",
        "promotionStartDateTo": "{data_end_time}",
    }
    assert items[rt.COUPON_PERFORMANCE].days == 89
    assert items[rt.COUPON_PERFORMANCE].report_options == {
        "couponStartDateFrom": "{data_start_time}",
        "couponStartDateTo": "{data_end_time}",
    }
