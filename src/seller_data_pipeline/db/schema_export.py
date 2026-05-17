from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.common.exceptions import AzureSqlSchemaExportError
from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.db.connection import get_connection

DATABASE_INFO_SQL = """
SELECT
    DB_NAME() AS database_name,
    SUSER_SNAME() AS login_name,
    CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)) AS server_name,
    CAST(SERVERPROPERTY('Edition') AS nvarchar(256)) AS edition;
"""

TABLES_SQL = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    t.object_id,
    t.create_date,
    t.modify_date
FROM sys.tables AS t
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name;
"""

COLUMNS_SQL = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    c.column_id,
    c.name AS column_name,
    ty.name AS data_type,
    CASE
        WHEN c.max_length = -1 THEN -1
        WHEN ty.name IN ('nvarchar', 'nchar') THEN c.max_length / 2
        ELSE c.max_length
    END AS max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    c.is_identity,
    CONVERT(nvarchar(100), ic.seed_value) AS identity_seed,
    CONVERT(nvarchar(100), ic.increment_value) AS identity_increment,
    dc.name AS default_constraint_name,
    dc.definition AS default_definition
FROM sys.tables AS t
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
INNER JOIN sys.columns AS c ON c.object_id = t.object_id
INNER JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
LEFT JOIN sys.identity_columns AS ic
    ON ic.object_id = c.object_id
   AND ic.column_id = c.column_id
LEFT JOIN sys.default_constraints AS dc
    ON dc.object_id = c.default_object_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name, c.column_id;
"""

INDEX_COLUMNS_SQL = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    i.name AS index_name,
    i.type_desc,
    i.is_unique,
    i.is_primary_key,
    i.is_unique_constraint,
    i.has_filter,
    i.filter_definition,
    ic.key_ordinal,
    ic.index_column_id,
    ic.is_included_column,
    ic.is_descending_key,
    c.name AS column_name
FROM sys.tables AS t
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
INNER JOIN sys.indexes AS i ON i.object_id = t.object_id
INNER JOIN sys.index_columns AS ic
    ON ic.object_id = i.object_id
   AND ic.index_id = i.index_id
INNER JOIN sys.columns AS c
    ON c.object_id = ic.object_id
   AND c.column_id = ic.column_id
WHERE t.is_ms_shipped = 0
  AND i.name IS NOT NULL
  AND i.is_hypothetical = 0
ORDER BY s.name, t.name, i.name, ic.is_included_column, ic.key_ordinal, ic.index_column_id;
"""

KEY_CONSTRAINTS_SQL = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    kc.name AS constraint_name,
    kc.type AS constraint_type,
    kc.type_desc AS constraint_type_desc,
    i.name AS backing_index_name
FROM sys.key_constraints AS kc
INNER JOIN sys.tables AS t ON t.object_id = kc.parent_object_id
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
LEFT JOIN sys.indexes AS i
    ON i.object_id = kc.parent_object_id
   AND i.index_id = kc.unique_index_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name, kc.name;
"""

FOREIGN_KEY_COLUMNS_SQL = """
SELECT
    fk.name AS foreign_key_name,
    ps.name AS parent_schema_name,
    pt.name AS parent_table_name,
    pc.name AS parent_column_name,
    rs.name AS referenced_schema_name,
    rt.name AS referenced_table_name,
    rc.name AS referenced_column_name,
    fkc.constraint_column_id,
    fk.delete_referential_action_desc,
    fk.update_referential_action_desc,
    fk.is_disabled,
    fk.is_not_trusted
FROM sys.foreign_keys AS fk
INNER JOIN sys.tables AS pt ON pt.object_id = fk.parent_object_id
INNER JOIN sys.schemas AS ps ON ps.schema_id = pt.schema_id
INNER JOIN sys.tables AS rt ON rt.object_id = fk.referenced_object_id
INNER JOIN sys.schemas AS rs ON rs.schema_id = rt.schema_id
INNER JOIN sys.foreign_key_columns AS fkc
    ON fkc.constraint_object_id = fk.object_id
INNER JOIN sys.columns AS pc
    ON pc.object_id = fkc.parent_object_id
   AND pc.column_id = fkc.parent_column_id
INNER JOIN sys.columns AS rc
    ON rc.object_id = fkc.referenced_object_id
   AND rc.column_id = fkc.referenced_column_id
WHERE pt.is_ms_shipped = 0
ORDER BY ps.name, pt.name, fk.name, fkc.constraint_column_id;
"""

ROW_COUNTS_SQL = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    SUM(CASE WHEN p.index_id IN (0, 1) THEN p.row_count ELSE 0 END) AS row_count
FROM sys.tables AS t
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
INNER JOIN sys.dm_db_partition_stats AS p ON p.object_id = t.object_id
WHERE t.is_ms_shipped = 0
GROUP BY s.name, t.name
ORDER BY s.name, t.name;
"""


def rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [
        {column: json_ready(value) for column, value in zip(columns, row, strict=False)}
        for row in cursor.fetchall()
    ]


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def execute_query(connection: Any, sql: str, *, query_name: str) -> list[dict[str, Any]]:
    cursor = connection.cursor()
    try:
        cursor.execute(sql)
        return rows_to_dicts(cursor)
    except Exception as exc:
        raise AzureSqlSchemaExportError(
            "Azure SQL live schema export failed while reading "
            f"{query_name}. If the original error mentions `ODBC SQL type ... "
            "is not yet supported`, a system catalog query may be returning a "
            "driver-specific SQL Server type and should cast that column to a "
            f"plain text or numeric type. Original error: {exc}"
        ) from exc
    finally:
        cursor.close()


def fetch_live_schema_snapshot(
    *,
    settings: Settings | None = None,
    include_row_counts: bool = False,
) -> dict[str, Any]:
    """Read the current Azure SQL schema from system catalog views.

    The returned payload is intentionally factual and implementation-oriented. It
    is suitable for comparing live database state with
    docs/database/database_current_schema_spec.md, but it does not replace the
    curated spec because the spec also includes human field descriptions and
    data-source notes.
    """

    with get_connection(settings=settings) as connection:
        database_info_rows = execute_query(
            connection, DATABASE_INFO_SQL, query_name="database info"
        )
        raw_snapshot = {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "database": database_info_rows[0] if database_info_rows else {},
            "tables": execute_query(connection, TABLES_SQL, query_name="tables catalog"),
            "columns": execute_query(connection, COLUMNS_SQL, query_name="columns catalog"),
            "index_columns": execute_query(
                connection, INDEX_COLUMNS_SQL, query_name="index columns catalog"
            ),
            "key_constraints": execute_query(
                connection, KEY_CONSTRAINTS_SQL, query_name="key constraints catalog"
            ),
            "foreign_key_columns": execute_query(
                connection, FOREIGN_KEY_COLUMNS_SQL, query_name="foreign key columns catalog"
            ),
            "row_counts": (
                execute_query(connection, ROW_COUNTS_SQL, query_name="row counts DMV")
                if include_row_counts
                else []
            ),
        }

    return normalise_schema_snapshot(raw_snapshot)


def normalise_schema_snapshot(raw_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Group flat catalog rows into table-centric schema metadata."""

    tables_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for table in raw_snapshot.get("tables", []):
        key = (table["schema_name"], table["table_name"])
        tables_by_key[key] = {
            "schema_name": table["schema_name"],
            "table_name": table["table_name"],
            "object_id": table.get("object_id"),
            "create_date": table.get("create_date"),
            "modify_date": table.get("modify_date"),
            "row_count": None,
            "columns": [],
            "indexes": [],
            "key_constraints": [],
            "foreign_keys": [],
        }

    for row in raw_snapshot.get("row_counts", []):
        table = tables_by_key.get((row["schema_name"], row["table_name"]))
        if table is not None:
            table["row_count"] = row.get("row_count")

    for column in raw_snapshot.get("columns", []):
        table = tables_by_key.get((column["schema_name"], column["table_name"]))
        if table is not None:
            table["columns"].append(column)

    indexes_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in raw_snapshot.get("index_columns", []):
        key = (row["schema_name"], row["table_name"], row["index_name"])
        index = indexes_by_key.setdefault(
            key,
            {
                "schema_name": row["schema_name"],
                "table_name": row["table_name"],
                "index_name": row["index_name"],
                "type_desc": row.get("type_desc"),
                "is_unique": row.get("is_unique"),
                "is_primary_key": row.get("is_primary_key"),
                "is_unique_constraint": row.get("is_unique_constraint"),
                "has_filter": row.get("has_filter"),
                "filter_definition": row.get("filter_definition"),
                "key_columns": [],
                "included_columns": [],
            },
        )
        column_spec = {
            "column_name": row["column_name"],
            "is_descending_key": row.get("is_descending_key"),
            "key_ordinal": row.get("key_ordinal"),
            "index_column_id": row.get("index_column_id"),
        }
        if row.get("is_included_column"):
            index["included_columns"].append(column_spec)
        else:
            index["key_columns"].append(column_spec)

    for index in indexes_by_key.values():
        index["key_columns"].sort(key=lambda value: value.get("key_ordinal") or 0)
        index["included_columns"].sort(key=lambda value: value.get("index_column_id") or 0)
        table = tables_by_key.get((index["schema_name"], index["table_name"]))
        if table is not None:
            table["indexes"].append(index)

    for table in tables_by_key.values():
        table["indexes"].sort(key=lambda value: value["index_name"])

    for constraint in raw_snapshot.get("key_constraints", []):
        table = tables_by_key.get((constraint["schema_name"], constraint["table_name"]))
        if table is not None:
            table["key_constraints"].append(constraint)

    foreign_keys_by_name: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in raw_snapshot.get("foreign_key_columns", []):
        key = (row["parent_schema_name"], row["parent_table_name"], row["foreign_key_name"])
        foreign_key = foreign_keys_by_name.setdefault(
            key,
            {
                "foreign_key_name": row["foreign_key_name"],
                "parent_schema_name": row["parent_schema_name"],
                "parent_table_name": row["parent_table_name"],
                "referenced_schema_name": row["referenced_schema_name"],
                "referenced_table_name": row["referenced_table_name"],
                "delete_referential_action_desc": row.get("delete_referential_action_desc"),
                "update_referential_action_desc": row.get("update_referential_action_desc"),
                "is_disabled": row.get("is_disabled"),
                "is_not_trusted": row.get("is_not_trusted"),
                "columns": [],
            },
        )
        foreign_key["columns"].append(
            {
                "constraint_column_id": row.get("constraint_column_id"),
                "parent_column_name": row["parent_column_name"],
                "referenced_column_name": row["referenced_column_name"],
            }
        )

    for foreign_key in foreign_keys_by_name.values():
        foreign_key["columns"].sort(key=lambda value: value.get("constraint_column_id") or 0)
        table = tables_by_key.get(
            (foreign_key["parent_schema_name"], foreign_key["parent_table_name"])
        )
        if table is not None:
            table["foreign_keys"].append(foreign_key)

    return {
        "generated_at_utc": raw_snapshot.get("generated_at_utc"),
        "database": raw_snapshot.get("database", {}),
        "table_count": len(tables_by_key),
        "tables": list(tables_by_key.values()),
    }


def sql_type_label(column: dict[str, Any]) -> str:
    data_type = str(column.get("data_type") or "").upper()
    max_length = column.get("max_length")
    precision = column.get("precision")
    scale = column.get("scale")

    if data_type in {"NVARCHAR", "NCHAR", "VARCHAR", "CHAR", "VARBINARY", "BINARY"}:
        length = "MAX" if max_length == -1 else str(max_length)
        return f"{data_type}({length})"
    if data_type in {"DECIMAL", "NUMERIC"}:
        return f"{data_type}({precision},{scale})"
    if data_type in {"DATETIME2", "TIME", "DATETIMEOFFSET"} and scale is not None:
        return f"{data_type}({scale})"
    return data_type


def format_index_columns(columns: list[dict[str, Any]]) -> str:
    values = []
    for column in columns:
        suffix = " DESC" if column.get("is_descending_key") else ""
        values.append(f"`{column['column_name']}`{suffix}")
    return ", ".join(values) if values else ""


def render_schema_markdown(snapshot: dict[str, Any]) -> str:
    database = snapshot.get("database", {})
    lines = [
        "# Azure SQL Live Schema Export",
        "",
        "> This file is generated from the live Azure SQL system catalog. ",
        "> Use it as an input when updating `docs/database/database_current_schema_spec.md`; ",
        "> it is not a replacement for the curated spec because it does not contain all human field descriptions.",
        "",
        "## Database",
        "",
        f"- Generated at UTC: `{snapshot.get('generated_at_utc')}`",
        f"- Database: `{database.get('database_name', '')}`",
        f"- Server: `{database.get('server_name', '')}`",
        f"- Edition: `{database.get('edition', '')}`",
        f"- Login: `{database.get('login_name', '')}`",
        f"- User tables: `{snapshot.get('table_count', 0)}`",
        "",
        "## Table Summary",
        "",
        "| Table | Columns | Indexes | Key constraints | Foreign keys | Row count |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for table in snapshot.get("tables", []):
        row_count = table.get("row_count")
        lines.append(
            "| "
            f"`{table['schema_name']}.{table['table_name']}` | "
            f"{len(table.get('columns', []))} | "
            f"{len(table.get('indexes', []))} | "
            f"{len(table.get('key_constraints', []))} | "
            f"{len(table.get('foreign_keys', []))} | "
            f"{row_count if row_count is not None else ''} |"
        )

    lines.extend(["", "## Tables", ""])

    for table in snapshot.get("tables", []):
        lines.extend(
            [
                f"### `{table['schema_name']}.{table['table_name']}`",
                "",
                f"- Create date: `{table.get('create_date')}`",
                f"- Modify date: `{table.get('modify_date')}`",
            ]
        )
        if table.get("row_count") is not None:
            lines.append(f"- Row count: `{table['row_count']}`")
        lines.extend(
            [
                "",
                "#### Columns",
                "",
                "| # | Column | Type | Nullable | Identity | Default |",
                "|---:|---|---|---|---|---|",
            ]
        )
        for column in table.get("columns", []):
            identity = "yes" if column.get("is_identity") else ""
            if column.get("is_identity"):
                identity = (
                    f"seed={column.get('identity_seed')}, "
                    f"increment={column.get('identity_increment')}"
                )
            default = str(column.get("default_definition") or "").replace("|", "\\|")
            lines.append(
                "| "
                f"{column['column_id']} | "
                f"`{column['column_name']}` | "
                f"`{sql_type_label(column)}` | "
                f"{'YES' if column.get('is_nullable') else 'NO'} | "
                f"{identity} | "
                f"`{default}` |"
            )

        if table.get("indexes"):
            lines.extend(
                [
                    "",
                    "#### Indexes",
                    "",
                    "| Index | Unique | Type | Key columns | Included columns | Filter |",
                    "|---|---|---|---|---|---|",
                ]
            )
            for index in table.get("indexes", []):
                included_columns = format_index_columns(index.get("included_columns", []))
                filter_definition = str(index.get("filter_definition") or "").replace("|", "\\|")
                lines.append(
                    "| "
                    f"`{index['index_name']}` | "
                    f"{'YES' if index.get('is_unique') else 'NO'} | "
                    f"`{index.get('type_desc')}` | "
                    f"{format_index_columns(index.get('key_columns', []))} | "
                    f"{included_columns} | "
                    f"`{filter_definition}` |"
                )

        if table.get("key_constraints"):
            lines.extend(
                [
                    "",
                    "#### Key constraints",
                    "",
                    "| Constraint | Type | Backing index |",
                    "|---|---|---|",
                ]
            )
            for constraint in table.get("key_constraints", []):
                lines.append(
                    "| "
                    f"`{constraint['constraint_name']}` | "
                    f"`{constraint.get('constraint_type_desc')}` | "
                    f"`{constraint.get('backing_index_name') or ''}` |"
                )

        if table.get("foreign_keys"):
            lines.extend(
                [
                    "",
                    "#### Foreign keys",
                    "",
                    "| Foreign key | Columns | References | Delete | Update | Disabled | Not trusted |",
                    "|---|---|---|---|---|---|---|",
                ]
            )
            for foreign_key in table.get("foreign_keys", []):
                parent_columns = ", ".join(
                    f"`{column['parent_column_name']}`" for column in foreign_key.get("columns", [])
                )
                referenced_columns = ", ".join(
                    f"`{column['referenced_column_name']}`"
                    for column in foreign_key.get("columns", [])
                )
                referenced_table = (
                    f"`{foreign_key['referenced_schema_name']}."
                    f"{foreign_key['referenced_table_name']}`"
                )
                lines.append(
                    "| "
                    f"`{foreign_key['foreign_key_name']}` | "
                    f"{parent_columns} | "
                    f"{referenced_table} ({referenced_columns}) | "
                    f"`{foreign_key.get('delete_referential_action_desc')}` | "
                    f"`{foreign_key.get('update_referential_action_desc')}` | "
                    f"{'YES' if foreign_key.get('is_disabled') else 'NO'} | "
                    f"{'YES' if foreign_key.get('is_not_trusted') else 'NO'} |"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_schema_exports(
    snapshot: dict[str, Any],
    *,
    output_dir: Path,
    output_prefix: str,
    output_format: str,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    if output_format in {"json", "both"}:
        json_path = output_dir / f"{output_prefix}.json"
        json_path.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=False),
            encoding="utf-8",
        )
        written["json"] = json_path

    if output_format in {"markdown", "both"}:
        markdown_path = output_dir / f"{output_prefix}.md"
        markdown_path.write_text(render_schema_markdown(snapshot), encoding="utf-8")
        written["markdown"] = markdown_path

    return written
