from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from seller_data_pipeline.parsers.amazon.settlement_report_parser import (
    SETTLEMENT_V2_REPORT_TYPE,
    SettlementReportParser,
)


@dataclass(frozen=True)
class SettlementFileSummary:
    raw_file_path: str
    row_count: int
    transaction_row_count: int
    summary_row_count: int


@dataclass(frozen=True)
class SettlementAggregateAnalysis:
    report_type: str
    marketplace_id: str
    raw_file_count: int
    row_count: int
    transaction_row_count: int
    summary_row_count: int
    file_summaries: list[SettlementFileSummary]
    transaction_type_counts: Counter[str]
    amount_type_counts: Counter[str]
    amount_description_counts: Counter[str]
    amount_category_counts: Counter[str]
    profit_bucket_counts: Counter[str]
    combination_counts: Counter[tuple[str, str, str, str, str]]


def analyze_settlement_report_files(
    *,
    raw_file_paths: list[str | Path],
    marketplace_id: str,
) -> SettlementAggregateAnalysis:
    parser = SettlementReportParser()
    file_summaries: list[SettlementFileSummary] = []
    transaction_type_counts: Counter[str] = Counter()
    amount_type_counts: Counter[str] = Counter()
    amount_description_counts: Counter[str] = Counter()
    amount_category_counts: Counter[str] = Counter()
    profit_bucket_counts: Counter[str] = Counter()
    combination_counts: Counter[tuple[str, str, str, str, str]] = Counter()

    row_count = 0
    transaction_row_count = 0
    summary_row_count = 0

    for raw_file_path in raw_file_paths:
        path = Path(raw_file_path)
        records = parser.parse_file(raw_file_path=path, marketplace_id=marketplace_id)
        file_summary_rows = sum(1 for record in records if record.is_settlement_summary)
        file_transaction_rows = len(records) - file_summary_rows
        file_summaries.append(
            SettlementFileSummary(
                raw_file_path=str(path),
                row_count=len(records),
                transaction_row_count=file_transaction_rows,
                summary_row_count=file_summary_rows,
            )
        )
        row_count += len(records)
        transaction_row_count += file_transaction_rows
        summary_row_count += file_summary_rows

        for record in records:
            transaction_type = record.transaction_type or "<blank>"
            amount_type = record.amount_type or "<blank>"
            amount_description = record.amount_description or "<blank>"
            transaction_type_counts[transaction_type] += 1
            amount_type_counts[amount_type] += 1
            amount_description_counts[amount_description] += 1
            amount_category_counts[record.amount_category] += 1
            profit_bucket_counts[record.profit_bucket] += 1
            combination_counts[
                (
                    transaction_type,
                    amount_type,
                    amount_description,
                    record.amount_category,
                    record.profit_bucket,
                )
            ] += 1

    return SettlementAggregateAnalysis(
        report_type=SETTLEMENT_V2_REPORT_TYPE,
        marketplace_id=marketplace_id,
        raw_file_count=len(raw_file_paths),
        row_count=row_count,
        transaction_row_count=transaction_row_count,
        summary_row_count=summary_row_count,
        file_summaries=file_summaries,
        transaction_type_counts=transaction_type_counts,
        amount_type_counts=amount_type_counts,
        amount_description_counts=amount_description_counts,
        amount_category_counts=amount_category_counts,
        profit_bucket_counts=profit_bucket_counts,
        combination_counts=combination_counts,
    )


def render_settlement_aggregate_markdown(analysis: SettlementAggregateAnalysis) -> str:
    lines = [
        f"# {analysis.report_type} 聚合取样记录",
        "",
        "> 本文件基于已下载的多份 Amazon settlement raw report 生成。",
        "> 原始报告文件可能包含经营数据，不应提交 GitHub；本文只保留字段结构、计数和分类建议。",
        "",
        "## 1. 样例元数据",
        "",
        "| 项目 | 值 |",
        "|---|---|",
        "| source_system | `sp_api_reports` |",
        f"| report_type | `{analysis.report_type}` |",
        f"| marketplace_id | `{analysis.marketplace_id}` |",
        f"| raw_file_count | `{analysis.raw_file_count}` |",
        f"| row_count | `{analysis.row_count}` |",
        f"| transaction_row_count | `{analysis.transaction_row_count}` |",
        f"| settlement_summary_row_count | `{analysis.summary_row_count}` |",
        "",
        "## 2. 文件级统计",
        "",
        "| raw_file_path | rows | transaction_rows | summary_rows |",
        "|---|---:|---:|---:|",
    ]
    for item in analysis.file_summaries:
        lines.append(
            f"| `{item.raw_file_path}` | {item.row_count} | "
            f"{item.transaction_row_count} | {item.summary_row_count} |"
        )

    lines.extend(
        [
            "",
            "## 3. transaction-type 分布",
            "",
            _render_counter_table(analysis.transaction_type_counts, "transaction_type"),
            "",
            "## 4. amount-type 分布",
            "",
            _render_counter_table(analysis.amount_type_counts, "amount_type"),
            "",
            "## 5. amount-description 分布",
            "",
            _render_counter_table(analysis.amount_description_counts, "amount_description"),
            "",
            "## 6. 第一版分类分布",
            "",
            "### 6.1 profit_bucket",
            "",
            _render_counter_table(analysis.profit_bucket_counts, "profit_bucket"),
            "",
            "### 6.2 amount_category",
            "",
            _render_counter_table(analysis.amount_category_counts, "amount_category"),
            "",
            "## 7. 组合映射样例",
            "",
            (
                "| transaction_type | amount_type | amount_description | "
                "amount_category | profit_bucket | rows |"
            ),
            "|---|---|---|---|---|---:|",
        ]
    )
    for combination, count in analysis.combination_counts.most_common(80):
        (
            transaction_type,
            amount_type,
            amount_description,
            amount_category,
            profit_bucket,
        ) = combination
        lines.append(
            f"| `{transaction_type}` | `{amount_type}` | `{amount_description}` | "
            f"`{amount_category}` | `{profit_bucket}` | {count} |"
        )

    lines.extend(
        [
            "",
            "## 8. 初步结论",
            "",
            (
                "1. 结算报告第一行通常是 settlement summary 行，带结算周期、"
                "币种和 total amount；后续明细行这些列可能为空。"
                "Parser 需要把 summary 元数据向下继承到交易明细。"
            ),
            (
                "2. `amount-type` + `amount-description` + `transaction-type` "
                "足以建立第一版费用分类字典，但这只是运营分析分类，"
                "不应直接等同会计最终科目。"
            ),
            (
                "3. `Cost of Advertising` 已经出现在 settlement 中，后续仍建议再接 "
                "Ads API 获取 campaign / keyword 维度表现；"
                "settlement 主要用于财务入账口径。"
            ),
            (
                "4. Coupon、Deal、Storage Fee、Subscription Fee、"
                "FBA Inbound Placement Service Fee、Inventory Reimbursement、"
                "Liquidations 都已在样例中出现，应在数据库 spec 中保留分类字段。"
            ),
            "",
            "## 9. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            (
                "| `amazon_settlement_transaction` | `sampling` | "
                "已有多份真实样例，可保存逐行 settlement 明细和第一版分类字段 |"
            ),
            (
                "| `amazon_finance_event` | `draft` | "
                "后续从 settlement 明细聚合/归类而来，需等分类规则稳定后确认 |"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def _render_counter_table(counter: Counter[str], column_name: str) -> str:
    lines = [f"| {column_name} | rows |", "|---|---:|"]
    for value, count in counter.most_common():
        lines.append(f"| `{value}` | {count} |")
    return "\n".join(lines)
