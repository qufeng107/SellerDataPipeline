from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from seller_data_pipeline.reports.monthly_reporting_common import (
    DARK_BLUE,
    GREEN_FILL,
    HEADER_BLUE,
    LIGHT_BLUE,
    MID_BLUE,
    MONEY_FORMAT,
    WHITE,
    YELLOW_FILL,
    as_bool,
    as_decimal,
    summarize_finance_rows,
)

if TYPE_CHECKING:
    from seller_data_pipeline.services.monthly_financial_close_service import (
        MonthlyFinancialCloseResult,
    )

ZERO = Decimal("0")
KNOWN_ACCOUNTING_TYPES = {
    "Shipment",
    "Refund",
    "RemovalShipment",
    "ServiceFee",
    "FBAInventoryReimbursement",
    "MiscellaneousLedgerAdjustment",
    "ProductAdsPayment",
    "Transfer",
    "Retrocharge",
}


def build_accountant_monthly_workbook(
    result: MonthlyFinancialCloseResult,
    finance_rows: Sequence[Mapping[str, Any]],
) -> Workbook:
    workbook = Workbook()
    workbook.remove(workbook.active)
    summary = workbook.create_sheet("01_会计汇总")
    classified = workbook.create_sheet("02_分类明细")
    source = workbook.create_sheet("03_源交易明细")
    checks = workbook.create_sheet("04_核验与说明")

    components = summarize_finance_rows(finance_rows)
    classified_rows = [_classify_row(row) for row in finance_rows]
    _write_summary(summary, result, components, finance_rows)
    _write_classified(classified, classified_rows)
    _write_source(source, finance_rows)
    _write_checks(checks, result, finance_rows, classified_rows, components)
    workbook.active = 0
    return workbook


def _write_summary(
    sheet: Any,
    result: MonthlyFinancialCloseResult,
    components: Mapping[str, Decimal],
    finance_rows: Sequence[Mapping[str, Any]],
) -> None:
    nm = result.natural_month_finance
    sheet.merge_cells("A1:F1")
    sheet["A1"] = f"{result.month} Amazon 会计月度底稿"
    _title(sheet["A1"], 16)
    sheet.merge_cells("A2:F2")
    sheet["A2"] = (
        "主源：normalized Finances natural-month ledger；本表用于会计做账辅助和交易追溯，"
        "不等同于法定财务报表或税务申报表。"
    )
    _fill_range(sheet, "A2:F2", LIGHT_BLUE)
    sheet["A2"].alignment = Alignment(wrap_text=True)

    metadata = (
        ("月份", result.month),
        ("Marketplace", result.marketplace_id),
        ("Source row count", len(finance_rows)),
        ("币种", result.currency or "USD"),
        ("记账汇率 USD/CNY", None),
    )
    for row, (label, value) in enumerate(metadata, 4):
        sheet.cell(row, 1, label)
        sheet.cell(row, 2, value)
    _header_pair(sheet, "A4:B4")
    sheet["B8"].fill = PatternFill("solid", fgColor=YELLOW_FILL)
    sheet["B8"].alignment = Alignment(horizontal="center")
    sheet["B8"] = None

    status_rows = (
        ("Released + Deferred", "已由natural-month lifecycle policy去重纳入", "不可只筛Released"),
        ("Transfer", "排除损益", "仅现金/银行回款参考"),
        ("商品成本", "SKU effective-date cost", "不再使用固定30 RMB/件历史算法"),
        ("Adjustment / Reimbursement", "不自动重复扣COGS", "只有明确库存损失证据才单独write-off"),
    )
    sheet["D4"] = "关键口径"
    sheet["E4"] = "状态"
    sheet["F4"] = "说明"
    _header_row(sheet, 4, 4, 6)
    for row, values in enumerate(status_rows, 5):
        for col, value in enumerate(values, 4):
            sheet.cell(row, col, value)
        sheet.cell(row, 6).alignment = Alignment(wrap_text=True)

    _section(sheet, 10, "会计项目汇总", 6)
    headers = ("会计项目", "金额USD", "金额CNY", "方向", "建议科目", "说明")
    for col, value in enumerate(headers, 1):
        sheet.cell(11, col, value)
    _header_row(sheet, 11, 1, 6)

    if nm is None:
        summary_rows: tuple[tuple[str, Decimal, str, str, str], ...] = ()
    else:
        posted_ads = components.get("posted_ads_reference", nm.finances_ads_charge_reference)
        amazon_net = nm.operating_net_before_ads_replacement + posted_ads
        reference_profit = amazon_net - nm.landed_cogs
        summary_rows = (
            ("商品销售收入", nm.product_sales_amount, "收入", "主营业务收入", "Shipment / product sales"),
            ("运费收入", components.get("shipping_income", ZERO), "收入", "主营业务收入-运费", "Shipment / shipping"),
            ("订单促销折扣", components.get("order_promotion", ZERO), "收入冲减/费用", "销售折让或促销费", "Shipment / promo rebates"),
            ("FBA单件履约费", components.get("fba_fulfillment", ZERO), "费用", "销售费用-FBA履约费", "Shipment / FBA fulfillment"),
            ("Shipping Chargeback", components.get("shipping_chargeback", ZERO), "费用", "销售费用-FBA履约费", "Shipment shipping chargeback"),
            ("净销售佣金", components.get("net_commission", ZERO), "费用", "销售费用-平台佣金", "Commission/Base + Commission/Promo"),
            ("退款净额", nm.refund_total, "收入冲减", "销售退回/销售折让", "Refund transaction net"),
            ("广告账单净额（posted-date）", posted_ads, "费用", "销售费用-广告费", "Finances ProductAdsPayment；不是当月投放消耗"),
            ("店铺订阅费", nm.subscription_fee, "费用", "销售费用-平台服务费", "Subscription"),
            ("Coupon费用", nm.coupon_fee, "费用", "销售费用-促销费", "participation + performance"),
            ("Deal费用", nm.deal_fee, "费用", "销售费用-促销费", "participation + performance"),
            ("仓储费", nm.storage_fee, "费用", "销售费用-FBA仓储费", "Storage fee"),
            ("客户退货处理费", nm.customer_return_fee, "费用", "销售费用-FBA服务费", "Customer return / HRR"),
            ("其他Service Fee", nm.other_service_fee, "费用", "销售费用-其他平台费", "Other ServiceFee"),
            ("赔偿收入净额", nm.reimbursement_total, "其他收益", "其他收益或费用冲减", "FBA inventory reimbursement"),
            ("其他账务调整", nm.adjustment_total, "其他收益/调整", "其他收益或费用冲减", "Miscellaneous ledger adjustment"),
            ("库存清算净额", nm.liquidation_total, "其他收入", "其他业务收入/清算", "Liquidation revenue - fees"),
            ("Amazon交易净额（不含Transfer）", amazon_net, "小计", "Amazon往来净额", "Operating rows + posted-date ads billing"),
            ("商品采购成本", -nm.product_cost_cogs, "成本", "主营业务成本", "SKU effective-date product cost"),
            ("头程成本", -nm.first_mile_cogs, "成本", "主营业务成本-头程", "SKU effective-date first-mile"),
            ("包装成本", -nm.packaging_cogs, "成本", "主营业务成本", "SKU effective-date packaging"),
            ("其他单位成本", -nm.other_unit_cogs, "成本", "主营业务成本", "SKU effective-date other unit cost"),
            ("账单月参考利润", reference_profit, "参考", "管理/会计辅助", "Amazon交易净额 - 到岸COGS；非税务法定利润"),
            ("管理经营利润（备查）", nm.management_operating_profit, "备查", "不入会计主表", "经营月报口径；广告按Ads API实际发生"),
            ("Ads API当月广告消耗（备查）", -nm.ads_api_report_date_spend, "备查", "不替代账单凭证", "解释广告扣款时点差异"),
            (
                "Transfer（备查，不计损益）",
                _cash_transfer_display_amount(nm.transfer_reference),
                "备查",
                "银行/收款账户往来",
                "按Amazon账户资金流方向显示；打款转出为负数，不是收入或费用",
            ),
        )

    start = 12
    for row_index, (label, amount, direction, account, note) in enumerate(summary_rows, start):
        sheet.cell(row_index, 1, label)
        sheet.cell(row_index, 2, float(amount)).number_format = MONEY_FORMAT
        # CNY formula remains blank until the accountant explicitly enters B8 FX.
        sheet.cell(row_index, 3, f'=IF($B$8="","",B{row_index}*$B$8)')
        sheet.cell(row_index, 3).number_format = MONEY_FORMAT
        sheet.cell(row_index, 4, direction)
        sheet.cell(row_index, 5, account)
        sheet.cell(row_index, 6, note).alignment = Alignment(wrap_text=True)
        if label in {"Amazon交易净额（不含Transfer）", "账单月参考利润", "管理经营利润（备查）"}:
            _fill_range(sheet, f"A{row_index}:F{row_index}", GREEN_FILL)
            for cell in sheet[row_index][:6]:
                cell.font = Font(bold=True)

    _apply_widths(sheet, {"A": 34, "B": 17, "C": 17, "D": 18, "E": 30, "F": 48})
    sheet.freeze_panes = "A12"


def _write_classified(sheet: Any, rows: Sequence[Mapping[str, Any]]) -> None:
    headers = (
        "财务分类",
        "建议会计项目",
        "计入损益",
        "处理说明",
        "posted_date_local",
        "transaction_status",
        "transaction_type",
        "transaction_id",
        "order_id",
        "description",
        "amount",
        "currency",
        "management_role",
        "source_trace",
    )
    for col, value in enumerate(headers, 1):
        sheet.cell(1, col, value)
    _header_row(sheet, 1, 1, len(headers), dark=True)
    for row_index, row in enumerate(rows, 2):
        for col, header in enumerate(headers, 1):
            value = row.get(header)
            if header == "amount":
                value = float(as_decimal(value))
            sheet.cell(row_index, col, value)
        sheet.cell(row_index, 11).number_format = MONEY_FORMAT
        sheet.cell(row_index, 4).alignment = Alignment(wrap_text=True)
        sheet.cell(row_index, 10).alignment = Alignment(wrap_text=True)
        if row.get("计入损益") == "人工复核":
            _fill_range(sheet, f"A{row_index}:N{row_index}", YELLOW_FILL)
    _apply_widths(
        sheet,
        {
            "A": 22,
            "B": 28,
            "C": 14,
            "D": 42,
            "E": 18,
            "F": 20,
            "G": 24,
            "H": 42,
            "I": 24,
            "J": 42,
            "K": 16,
            "L": 12,
            "M": 28,
            "N": 46,
        },
    )
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:N{max(sheet.max_row, 1)}"


def _write_source(sheet: Any, rows: Sequence[Mapping[str, Any]]) -> None:
    headers = (
        "marketplace_id",
        "transaction_id",
        "transaction_status",
        "transaction_type",
        "description",
        "posted_at_utc",
        "posted_at_local",
        "posted_date_local",
        "marketplace_timezone",
        "amount",
        "currency",
        "settlement_id",
        "order_id",
        "deferred_transaction_id",
        "release_transaction_id",
        "management_role",
        "management_include",
        "management_replace_with_ads_api",
        "review_required",
        "product_sales_amount",
        "shipping_amount",
        "promotion_amount",
        "fba_fulfillment_fee",
        "shipping_chargeback",
        "refund_product_amount",
        "refund_shipping_amount",
        "refund_promotion_amount",
        "liquidation_revenue",
        "liquidation_fee",
        "subscription_fee",
        "coupon_fee",
        "deal_fee",
        "storage_fee",
        "customer_return_fee",
        "other_service_fee",
        "unit_events_json",
        "related_identifiers_json",
        "raw_transaction_hash",
        "business_key_hash",
    )
    for col, value in enumerate(headers, 1):
        sheet.cell(1, col, value)
    _header_row(sheet, 1, 1, len(headers), dark=True)
    money_headers = {
        "amount",
        "product_sales_amount",
        "shipping_amount",
        "promotion_amount",
        "fba_fulfillment_fee",
        "shipping_chargeback",
        "refund_product_amount",
        "refund_shipping_amount",
        "refund_promotion_amount",
        "liquidation_revenue",
        "liquidation_fee",
        "subscription_fee",
        "coupon_fee",
        "deal_fee",
        "storage_fee",
        "customer_return_fee",
        "other_service_fee",
    }
    for row_index, row in enumerate(rows, 2):
        for col, header in enumerate(headers, 1):
            value = row.get(header)
            if header in money_headers:
                value = float(as_decimal(value))
            elif header in {"management_include", "management_replace_with_ads_api", "review_required"}:
                value = bool(as_bool(value))
            elif value is not None and not isinstance(value, (str, int, float, bool)):
                value = str(value)
            sheet.cell(row_index, col, value)
            if header in money_headers:
                sheet.cell(row_index, col).number_format = MONEY_FORMAT
    for col in range(1, len(headers) + 1):
        letter = sheet.cell(1, col).column_letter
        sheet.column_dimensions[letter].width = 18
    sheet.column_dimensions["B"].width = 42
    sheet.column_dimensions["E"].width = 42
    sheet.column_dimensions["P"].width = 30
    sheet.column_dimensions["AJ"].width = 48
    sheet.column_dimensions["AK"].width = 48
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{sheet.cell(1, len(headers)).column_letter}{max(sheet.max_row, 1)}"


def _write_checks(
    sheet: Any,
    result: MonthlyFinancialCloseResult,
    finance_rows: Sequence[Mapping[str, Any]],
    classified_rows: Sequence[Mapping[str, Any]],
    components: Mapping[str, Decimal],
) -> None:
    nm = result.natural_month_finance
    sheet.merge_cells("A1:F1")
    sheet["A1"] = "核验与口径说明"
    _title(sheet["A1"], 16)
    headers = ("检查项", "结果", "实际值", "期望/规则", "状态", "说明")
    for col, value in enumerate(headers, 1):
        sheet.cell(3, col, value)
    _header_row(sheet, 3, 1, 6)

    classified_pnl = sum(
        (as_decimal(row.get("amount")) for row in classified_rows if row.get("计入损益") == "是"),
        ZERO,
    )
    unknown_nonzero = [
        row for row in classified_rows if row.get("计入损益") == "人工复核" and as_decimal(row.get("amount")) != ZERO
    ]
    expected_accounting = components.get("accounting_transaction_net", ZERO)
    cost_expected = (nm.product_sales_units + nm.liquidation_units) if nm else 0
    cost_actual = nm.costed_units if nm else 0

    checks = (
        ("源交易行数", len(finance_rows), len(classified_rows), "source rows = classified rows", "通过" if len(finance_rows) == len(classified_rows) else "需复核", "分类明细不得丢行"),
        ("会计损益分类金额", classified_pnl, expected_accounting, "classified P&L = operating rows + posted ads reference", "通过" if abs(classified_pnl - expected_accounting) < Decimal("0.01") else "需复核", "Transfer和历史release reference不进入损益"),
        (
            "Transfer",
            _cash_transfer_display_amount(components.get("transfer_reference", ZERO)),
            "排除损益",
            "cash reference only; payout outflow shown negative",
            "通过",
            "按Amazon账户资金流方向显示；不作为收入或费用",
        ),
        ("未知非零分类", len(unknown_nonzero), 0, "must be zero", "通过" if not unknown_nonzero else "需复核", "新transaction type/status不得静默忽略"),
        ("COGS成本覆盖", cost_actual, cost_expected, "costed units = sales + liquidation units", "通过" if nm and cost_actual == cost_expected and not nm.missing_cost_skus else "需复核", f"missing_cost_skus={list(nm.missing_cost_skus) if nm else []}"),
        ("Seller Central人工核验", str(result.raw_metadata.get("seller_central_monthly_transaction_reconciliation_status") or "not_provided"), "optional", "manual export missing does not block", "参考", "收到官方Monthly Transaction时可额外逐项reconcile"),
        ("广告口径", components.get("posted_ads_reference", ZERO), -(nm.ads_api_report_date_spend if nm else ZERO), "posted billing != Ads API spend is allowed", "参考", "会计账单时点与经营广告发生时点分开"),
        ("负数显示", "显式负号", "显式负号", "-$114.89 / -7.85%", "通过", "不依赖红色或括号"),
    )
    for row_index, values in enumerate(checks, 4):
        for col, value in enumerate(values, 1):
            if isinstance(value, Decimal):
                value = float(value)
            sheet.cell(row_index, col, value)
        if isinstance(values[1], Decimal):
            sheet.cell(row_index, 2).number_format = MONEY_FORMAT
        if isinstance(values[2], Decimal):
            sheet.cell(row_index, 3).number_format = MONEY_FORMAT
        sheet.cell(row_index, 6).alignment = Alignment(wrap_text=True)
        status = values[4]
        fill = GREEN_FILL if status == "通过" else YELLOW_FILL
        sheet.cell(row_index, 5).fill = PatternFill("solid", fgColor=fill)
        sheet.cell(row_index, 5).font = Font(bold=True)

    note_row = 4 + len(checks) + 2
    sheet.merge_cells(start_row=note_row, start_column=1, end_row=note_row + 3, end_column=6)
    sheet.cell(note_row, 1, (
        "会计底稿原则：USD是source-of-truth currency；CNY换算只在会计明确填写月度记账汇率后生成。"
        "成本使用amazon_sku_cost effective-date数据，不使用历史固定30 RMB/件 + 2.5 RMB/件算法。"
        "Adjustment/Reimbursement不会因为quantity字段存在就自动重复扣COGS。"
        "本底稿是做账辅助，不替代会计对科目、税务、发票和汇率的专业判断。"
    ))
    sheet.cell(note_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
    _fill_range(sheet, f"A{note_row}:F{note_row + 3}", LIGHT_BLUE)
    _apply_widths(sheet, {"A": 28, "B": 22, "C": 22, "D": 34, "E": 14, "F": 50})
    sheet.freeze_panes = "A4"


def _cash_transfer_display_amount(amount: Decimal) -> Decimal:
    """Display Amazon payout transfers using Seller Central cash-flow direction.

    The normalized Finances ledger keeps Transfer as a positive cash-reference amount,
    while Seller Central Monthly Transaction represents a payout from the Amazon
    balance as a negative amount. Accounting-facing views use the latter convention
    so the direction is explicit; the source sheet continues to preserve the raw
    normalized ledger amount.
    """

    if amount == ZERO:
        return ZERO
    return -abs(amount)


def _classify_row(row: Mapping[str, Any]) -> dict[str, Any]:
    transaction_type = str(row.get("transaction_type") or "")
    amount = as_decimal(row.get("amount"))
    management_include = as_bool(row.get("management_include"))
    replace_ads = as_bool(row.get("management_replace_with_ads_api"))
    role = str(row.get("management_role") or "")
    classification = "参考/非损益"
    accounting_item = "不计损益"
    include = "否"
    note = "Reference row only."

    if management_include:
        include = "是"
        if transaction_type == "Shipment":
            classification = "订单销售"
            accounting_item = "销售收入及订单级费用"
            note = "Natural-month de-duplicated Shipment row."
        elif transaction_type == "Refund":
            classification = "退款"
            accounting_item = "销售退回/销售折让"
            note = "Refund transaction net."
        elif transaction_type == "RemovalShipment":
            classification = "库存清算"
            accounting_item = "其他业务收入/清算"
            note = "Liquidation revenue and fees."
        elif transaction_type == "ServiceFee":
            classification, accounting_item = _service_fee_classification(row)
            note = "ServiceFee classified from extracted fee components."
        elif transaction_type == "FBAInventoryReimbursement":
            classification = "赔偿"
            accounting_item = "其他收益或费用冲减"
            note = "FBA inventory reimbursement net; no automatic duplicate COGS."
        elif transaction_type == "MiscellaneousLedgerAdjustment":
            classification = "账务调整"
            accounting_item = "其他收益/调整"
            note = "Miscellaneous ledger adjustment."
        else:
            classification = "未分类"
            accounting_item = "待复核"
            include = "人工复核"
            note = "Management-included non-zero row has an unknown accounting type."
    elif replace_ads:
        classification = "广告账单"
        accounting_item = "销售费用-广告费"
        include = "是"
        note = "Posted-date ProductAdsPayment; management report replaces it with Ads API spend."
    elif role == "cash_transfer_reference" or transaction_type == "Transfer":
        classification = "资金划转"
        accounting_item = "银行/收款账户往来"
        note = "Cash transfer reference; excluded from P&L."
    elif role == "zero_value_unit_cogs_reference":
        classification = "COGS数量参考"
        accounting_item = "不计损益"
        note = "Zero-value unit event used only for cost quantity completeness."
    elif transaction_type == "Retrocharge" or role in {"non_operating_reference", "prior_period_release_reference"}:
        classification = "历史/追溯参考"
        accounting_item = "不计损益"
        note = "Reference row excluded by lifecycle policy to avoid double counting."
    elif transaction_type not in KNOWN_ACCOUNTING_TYPES and amount != ZERO:
        classification = "未分类"
        accounting_item = "待复核"
        include = "人工复核"
        note = "Unknown non-zero transaction type; do not silently ignore."

    source_trace = "; ".join(
        part
        for part in (
            f"transaction_id={row.get('transaction_id')}" if row.get("transaction_id") else "",
            f"raw_hash={row.get('raw_transaction_hash')}" if row.get("raw_transaction_hash") else "",
            f"business_key={row.get('business_key_hash')}" if row.get("business_key_hash") else "",
        )
        if part
    )
    display_amount = (
        _cash_transfer_display_amount(amount)
        if role == "cash_transfer_reference" or transaction_type == "Transfer"
        else amount
    )

    return {
        "财务分类": classification,
        "建议会计项目": accounting_item,
        "计入损益": include,
        "处理说明": note,
        "posted_date_local": str(row.get("posted_date_local") or ""),
        "transaction_status": row.get("transaction_status"),
        "transaction_type": transaction_type,
        "transaction_id": row.get("transaction_id"),
        "order_id": row.get("order_id"),
        "description": row.get("description"),
        "amount": display_amount,
        "currency": row.get("currency"),
        "management_role": role,
        "source_trace": source_trace,
    }


def _service_fee_classification(row: Mapping[str, Any]) -> tuple[str, str]:
    candidates = (
        ("subscription_fee", "店铺订阅费", "销售费用-平台服务费"),
        ("coupon_fee", "Coupon费用", "销售费用-促销费"),
        ("deal_fee", "Deal费用", "销售费用-促销费"),
        ("storage_fee", "FBA仓储费", "销售费用-FBA仓储费"),
        ("customer_return_fee", "客户退货处理费", "销售费用-FBA服务费"),
        ("other_service_fee", "其他Service Fee", "销售费用-其他平台费"),
    )
    for key, classification, account in candidates:
        if as_decimal(row.get(key)) != ZERO:
            return classification, account
    return "其他Service Fee", "销售费用-其他平台费"


def _title(cell: Any, size: int) -> None:
    cell.fill = PatternFill("solid", fgColor=DARK_BLUE)
    cell.font = Font(bold=True, color=WHITE, size=size)


def _section(sheet: Any, row: int, title: str, columns: int) -> None:
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=columns)
    sheet.cell(row, 1, title)
    sheet.cell(row, 1).fill = PatternFill("solid", fgColor=MID_BLUE)
    sheet.cell(row, 1).font = Font(bold=True, color=WHITE)


def _header_pair(sheet: Any, cell_range: str) -> None:
    for row in sheet[cell_range]:
        for cell in row:
            cell.fill = PatternFill("solid", fgColor=HEADER_BLUE)
            cell.font = Font(bold=True)


def _header_row(sheet: Any, row: int, start_col: int, end_col: int, *, dark: bool = False) -> None:
    fill = DARK_BLUE if dark else HEADER_BLUE
    color = WHITE if dark else "000000"
    for col in range(start_col, end_col + 1):
        cell = sheet.cell(row, col)
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.font = Font(bold=True, color=color)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _fill_range(sheet: Any, cell_range: str, color: str) -> None:
    for row in sheet[cell_range]:
        for cell in row:
            cell.fill = PatternFill("solid", fgColor=color)


def _apply_widths(sheet: Any, widths: Mapping[str, float]) -> None:
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width


__all__ = ["build_accountant_monthly_workbook"]
