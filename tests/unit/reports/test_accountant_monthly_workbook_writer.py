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
        warehouse_lost_reimbursement_amount=Decimal("0.00"),
        inventory_loss_status="not_applicable",
        inventory_loss_units=0,
        inventory_loss_costed_units=0,
        inventory_loss_missing_cost_skus=(),
        inventory_loss_landed_cost=Decimal("0.00"),
        inventory_loss_details=(),
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
        if str(values[0] or "").startswith("Transfer（备查，不计损益）")
    )
    assert transfer_summary[1] == -1848.64

    classified_sheet = workbook["02_分类明细"]
    assert classified_sheet["K2"].value == -1848.64

    source = workbook["03_源交易明细"]
    # Source trace keeps the normalized Finances ledger amount unchanged.
    amount_header = next(
        cell.column for cell in source[1] if str(cell.value or "").endswith("/ amount")
    )
    assert source.cell(2, amount_header).value == 1848.64


def test_warehouse_lost_reimbursement_is_classified_separately() -> None:
    row = {
        "transaction_type": "FBAInventoryReimbursement",
        "description": "WAREHOUSE_LOST",
        "amount": Decimal("5.62"),
        "management_include": True,
        "management_replace_with_ads_api": False,
        "management_role": "operating",
    }

    classified = _classify_row(row)

    assert classified["财务分类"].startswith("仓库丢失赔偿")
    assert classified["计入损益"] == "是"
    assert classified["amount"] == Decimal("5.62")
    assert "单独核销" in classified["处理说明"]


def test_normal_reimbursement_does_not_claim_inventory_writeoff() -> None:
    row = {
        "transaction_type": "FBAInventoryReimbursement",
        "description": "REVERSAL_REIMBURSEMENT",
        "amount": Decimal("20.95"),
        "management_include": True,
        "management_replace_with_ads_api": False,
        "management_role": "operating",
    }

    classified = _classify_row(row)

    assert classified["财务分类"].startswith("普通FBA赔偿")
    assert "不因 quantity 字段自动重复扣 COGS" in classified["处理说明"]


def test_accounting_summary_deducts_verified_warehouse_loss_once() -> None:
    nm = _natural_month()
    nm.inventory_loss_status = "ok"
    nm.inventory_loss_units = 1
    nm.inventory_loss_costed_units = 1
    nm.inventory_loss_landed_cost = Decimal("4.70")
    nm.inventory_loss_details = (
        {
            "reimbursement_id": "R-1",
            "approval_date": "2026-05-20",
            "seller_sku": "SKU-LOST",
            "fnsku": "FNSKU-LOST",
            "quantity": 1,
            "reimbursement_amount": Decimal("5.62"),
            "resolved_cost_sku": "SKU-LOST",
            "landed_cost_writeoff": Decimal("4.70"),
            "status": "ok",
        },
    )
    nm.warehouse_lost_reimbursement_amount = Decimal("5.62")
    result = _result()
    result.natural_month_finance = nm

    finance_rows = [
        {
            "transaction_type": "ProductAdsPayment",
            "amount": Decimal("-984.21"),
            "management_include": False,
            "management_replace_with_ads_api": True,
            "management_role": "ads_charge_reference",
            "currency": "USD",
        }
    ]
    workbook = build_accountant_monthly_workbook(result, finance_rows)
    summary = workbook["01_会计汇总"]
    rows = {
        str(values[0] or ""): values
        for values in summary.iter_rows(values_only=True)
        if values and values[0]
    }

    writeoff = next(
        values for label, values in rows.items() if label.startswith("仓库丢失库存成本核销")
    )
    reference_profit = next(
        values for label, values in rows.items() if label.startswith("账单月参考利润")
    )

    assert writeoff[1] == -4.70
    # Fixture Amazon net is 576.05; 576.05 - 467.25 - 4.70 = 104.10.
    assert reference_profit[1] == 104.10

    checks = workbook["04_核验与说明"]
    detail_rows = list(checks.iter_rows(values_only=True))
    detail_header_index = next(
        index for index, values in enumerate(detail_rows)
        if values and values[0] == "赔偿ID / Reimbursement ID"
    )
    assert detail_rows[detail_header_index][6] == "状态 / Status"
    assert detail_rows[detail_header_index + 1][6] == "已应用 / Applied"
