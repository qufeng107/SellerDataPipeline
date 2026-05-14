from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdsReportSamplingPlanItem:
    """One Amazon Ads Reporting v3 sampling target."""

    report_type_id: str
    ad_product: str
    group_by: tuple[str, ...]
    columns: tuple[str, ...]
    label: str
    purpose: str
    days: int = 14
    time_unit: str = "DAILY"
    priority: int = 100
    notes: str = ""

    def operation_key(self) -> str:
        return ":".join(
            [
                self.ad_product,
                self.report_type_id,
                ",".join(self.group_by),
                str(self.days),
                self.time_unit,
            ]
        )


SPONSORED_PRODUCTS_AD_PRODUCT = "SPONSORED_PRODUCTS"

SP_CAMPAIGN_COLUMNS = (
    "date",
    "campaignId",
    "campaignName",
    "campaignStatus",
    "impressions",
    "clicks",
    "cost",
    "sales7d",
    "purchases7d",
    "unitsSoldClicks7d",
)
SP_TARGETING_COLUMNS = (
    "date",
    "campaignId",
    "campaignName",
    "adGroupId",
    "adGroupName",
    "keywordId",
    "keyword",
    "matchType",
    "targeting",
    "impressions",
    "clicks",
    "cost",
    "sales7d",
    "purchases7d",
    "unitsSoldClicks7d",
)
SP_SEARCH_TERM_COLUMNS = (
    "date",
    "campaignId",
    "campaignName",
    "adGroupId",
    "adGroupName",
    "keywordId",
    "keyword",
    "matchType",
    "searchTerm",
    "targeting",
    "impressions",
    "clicks",
    "cost",
    "sales7d",
    "purchases7d",
    "unitsSoldClicks7d",
)
SP_ADVERTISED_PRODUCT_COLUMNS = (
    "date",
    "campaignId",
    "campaignName",
    "adGroupId",
    "adGroupName",
    "advertisedAsin",
    "advertisedSku",
    "impressions",
    "clicks",
    "cost",
    "sales7d",
    "purchases7d",
    "unitsSoldClicks7d",
)
SP_PURCHASED_PRODUCT_COLUMNS = (
    "date",
    "campaignId",
    "campaignName",
    "adGroupId",
    "adGroupName",
    "purchasedAsin",
    "advertisedAsin",
    "advertisedSku",
    "sales7d",
    "purchases7d",
    "unitsSoldClicks7d",
)

CORE_ADS_SAMPLING_PLAN: tuple[AdsReportSamplingPlanItem, ...] = (
    AdsReportSamplingPlanItem(
        report_type_id="spCampaigns",
        ad_product=SPONSORED_PRODUCTS_AD_PRODUCT,
        group_by=("campaign",),
        columns=SP_CAMPAIGN_COLUMNS,
        label="Sponsored Products campaign report",
        purpose="Campaign-level impressions, clicks, cost, sales and orders.",
        priority=10,
    ),
    AdsReportSamplingPlanItem(
        report_type_id="spTargeting",
        ad_product=SPONSORED_PRODUCTS_AD_PRODUCT,
        group_by=("targeting",),
        columns=SP_TARGETING_COLUMNS,
        label="Sponsored Products targeting report",
        purpose="Keyword/target-level performance for bid and targeting optimization.",
        priority=20,
    ),
    AdsReportSamplingPlanItem(
        report_type_id="spSearchTerm",
        ad_product=SPONSORED_PRODUCTS_AD_PRODUCT,
        group_by=("searchTerm",),
        columns=SP_SEARCH_TERM_COLUMNS,
        label="Sponsored Products search term report",
        purpose="Customer search terms, spend, orders and sales for keyword mining.",
        priority=30,
    ),
    AdsReportSamplingPlanItem(
        report_type_id="spAdvertisedProduct",
        ad_product=SPONSORED_PRODUCTS_AD_PRODUCT,
        group_by=("advertiser",),
        columns=SP_ADVERTISED_PRODUCT_COLUMNS,
        label="Sponsored Products advertised product report",
        purpose="Advertised SKU/ASIN performance for product-level ad analysis.",
        priority=40,
        notes=(
            "If Amazon rejects groupBy=advertiser for this account, retry after sampling "
            "the exact error and adjust columns/groupBy from diagnostic output."
        ),
    ),
    AdsReportSamplingPlanItem(
        report_type_id="spPurchasedProduct",
        ad_product=SPONSORED_PRODUCTS_AD_PRODUCT,
        group_by=("asin",),
        columns=SP_PURCHASED_PRODUCT_COLUMNS,
        label="Sponsored Products purchased product report",
        purpose="Purchased ASIN attribution after ad clicks, useful for halo sales analysis.",
        priority=50,
    ),
)


def get_ads_sampling_plan() -> list[AdsReportSamplingPlanItem]:
    return sorted(CORE_ADS_SAMPLING_PLAN, key=lambda item: item.priority)


__all__ = ["AdsReportSamplingPlanItem", "CORE_ADS_SAMPLING_PLAN", "get_ads_sampling_plan"]
