from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.db.connection import get_connection

_GO_BATCH_SEPARATOR_RE = re.compile(r"^\s*GO(?:\s+(\d+))?\s*(?:--.*)?$", re.IGNORECASE)


@dataclass(frozen=True)
class SqlMigrationResult:
    file_path: Path
    batch_count: int
    executed_batch_count: int
    dry_run: bool


def split_tsql_batches(sql_text: str) -> list[str]:
    """Split a SQL Server script into executable batches.

    pyodbc sends text directly to SQL Server, while `GO` is a client-side batch
    separator used by tools such as SSMS and sqlcmd. This function removes those
    separators and returns executable batches. `GO 3` is supported by repeating
    the previous batch three times.
    """

    batches: list[str] = []
    current_lines: list[str] = []

    for line in sql_text.replace("\ufeff", "").splitlines():
        match = _GO_BATCH_SEPARATOR_RE.match(line)
        if match:
            batch = "\n".join(current_lines).strip()
            if batch:
                repeat_count = int(match.group(1) or "1")
                batches.extend([batch] * repeat_count)
            current_lines = []
            continue
        current_lines.append(line)

    final_batch = "\n".join(current_lines).strip()
    if final_batch:
        batches.append(final_batch)
    return batches


def read_sql_batches(file_path: str | Path) -> list[str]:
    path = Path(file_path)
    sql_text = path.read_text(encoding="utf-8")
    return split_tsql_batches(sql_text)


def execute_sql_batches(connection: Any, batches: list[str]) -> int:
    cursor = connection.cursor()
    executed_count = 0
    try:
        for batch in batches:
            cursor.execute(batch)
            executed_count += 1
    finally:
        cursor.close()
    return executed_count


def run_sql_file(
    file_path: str | Path,
    *,
    settings: Settings | None = None,
    dry_run: bool = False,
) -> SqlMigrationResult:
    path = Path(file_path)
    batches = read_sql_batches(path)
    if dry_run:
        return SqlMigrationResult(
            file_path=path,
            batch_count=len(batches),
            executed_batch_count=0,
            dry_run=True,
        )

    with get_connection(settings=settings, autocommit=False) as conn:
        try:
            executed_count = execute_sql_batches(conn, batches)
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    return SqlMigrationResult(
        file_path=path,
        batch_count=len(batches),
        executed_batch_count=executed_count,
        dry_run=False,
    )
