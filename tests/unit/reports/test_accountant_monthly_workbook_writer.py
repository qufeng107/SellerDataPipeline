from decimal import Decimal
from types import SimpleNamespace

from seller_data_pipeline.reports.accountant_monthly_workbook_writer import (
    _classify_row,
    build_accountant_monthly_workbook,
)


def _natural_month() -> SimpleNamespace:
    return SimpleNamespace(
        finances_ads_charge_reference=Decimal("-984.21"),
        operating_net_before_ads_replacement=Decimal("1560.26"),
        landed_cogs=Decimal("467.25"),
        product_sales_amount=Decimal("2316.38"),
        refund_total=Decimal("-355.95"),
        subscription_fee=Decimal("-25.78"),
        coupon_fee=Decimal("0"),
        deal_fee=Decimal("0"),
        storage_fee=Decimal("-36.79"),
        customer_return_fee=Decimal("0"),
        other_service_fee=Decimal("-0.24"),
        reimbursement_total=Decimal("61.04"),
        adjustment_total=Decimal("0"),
        liquidation_total=Decimal("2.30"),
        product_cost_cogs=Decimal("415.60"),
        first_mile_cogs=Decimal("51.65"),
        packaging_cogs=Decimal("0"),
        other_unit_cogs=Decimal("0"),
        management_operating_profit=Decimal("548.35"),
        ads_api_report_date_spend=Decimal("544.66"),
        transfer_reference=Decimal("1848.64"),
        product_sales_units=94,
        liquidation_units=5,
        costed_units=99,
        missing_cost_skus=(),
    )


def _result() -> SimpleNamespace:
    return SimpleNamespace(
        month="2026-05",
        marketplace_id="ATVPDKIKX0DER",
        currency="USD",
        natural_month_finance=_natural_month(),
        raw_metadata={},
    )


def _transfer_row() -> dict[str, object]:
    return {
        "marketplace_id": "ATVPDKIKX0DER",
        "transaction_id": "transfer-1",
        "transaction_status": "RELEASED",
        "transaction_type": "Transfer",
        "description": "Amazon payout",
        "posted_date_local": "2026-05-14",
        "amount": Decimal("1848.64"),
        "currency": "USD",
        "management_role": "cash_transfer_reference",
        "management_include": False,
        "management_replace_with_ads_api": False,
        "review_required": False,
    }


def test_transfer_is_negative_in_accounting_views_but_source_amount_is_preserved() -> None:
    row = _transfer_row()

    classified = _classify_row(row)
    assert classified["amount"] == Decimal("-1848.64")
    assert classified["计入损益"] == "否"

    workbook = build_accountant_monthly_workbook(_result(), [row])

    summary = workbook["01_会计汇总"]
    transfer_summary = next(
        values
        for values in summary.iter_rows(values_only=True)
        if values[0] == "Transfer（备查，不计损益）"
    )
    assert transfer_summary[1] == -1848.64

    classified_sheet = workbook["02_分类明细"]
    assert classified_sheet["K2"].value == -1848.64

    source = workbook["03_源交易明细"]
    # Source trace keeps the normalized Finances ledger amount unchanged.
    amount_header = next(cell.column for cell in source[1] if cell.value == "amount")
    assert source.cell(2, amount_header).value == 1848.64
