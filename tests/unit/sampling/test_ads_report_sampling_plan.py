from __future__ import annotations

from seller_data_pipeline.sampling.ads_report_sampling_plan import get_ads_sampling_plan


def test_ads_sampling_plan_contains_sp_core_reports() -> None:
    items = get_ads_sampling_plan()
    report_type_ids = [item.report_type_id for item in items]

    assert report_type_ids == [
        "spCampaigns",
        "spTargeting",
        "spSearchTerm",
        "spAdvertisedProduct",
        "spPurchasedProduct",
    ]
    assert all(item.ad_product == "SPONSORED_PRODUCTS" for item in items)
    assert all(item.columns for item in items)
    assert all(item.group_by for item in items)
