from __future__ import annotations

from seller_data_pipeline.parsers.amazon.settlement_report_parser import SettlementReportParser


class FinanceReportParser(SettlementReportParser):
    """Compatibility wrapper for finance-related Amazon report parsing.

    The first sampled finance data source is the Flat File V2 Settlement Report.
    Keep this wrapper so older imports can continue to use FinanceReportParser
    while the concrete parser lives in settlement_report_parser.py.
    """
