"""SQL dialect handling and utilities."""

from typing import Literal

import sqlglot


def parse_sql(query: str, dialect: Literal["postgres", "sqlite"]) -> sqlglot.Expression:
    """Parse SQL query into AST."""
    dialect_map = {"postgres": "postgres", "sqlite": "sqlite"}
    return sqlglot.parse_one(query, read=dialect_map[dialect])


def parse_schema(
    schema_ddl: str, dialect: Literal["postgres", "sqlite"]
) -> list[sqlglot.Expression]:
    """Parse schema DDL into list of AST nodes."""
    dialect_map = {"postgres": "postgres", "sqlite": "sqlite"}
    return sqlglot.parse(schema_ddl, read=dialect_map[dialect])


def extract_table_info(
    schema_ast: list[sqlglot.Expression], schema_ddl: str = ""
) -> dict[str, dict]:
    """Extract table information from schema AST."""
    tables: dict[str, dict] = {}
    row_hints: dict[str, int] = {}

    for stmt in schema_ast:
        if isinstance(stmt, sqlglot.expressions.Create):
            table_name = stmt.this.name if stmt.this else None
            if table_name:
                columns = []
                if hasattr(stmt, "expressions"):
                    for col in stmt.expressions:
                        if isinstance(col, sqlglot.expressions.ColumnDef):
                            col_name = col.this.name if col.this else None
                            col_type = col.kind.name if col.kind else None
                            if col_name:
                                columns.append({"name": col_name, "type": col_type})

                tables[table_name] = {
                    "columns": columns,
                    "indexes": [],
                }

    # Parse row hints from comments in schema DDL
    if schema_ddl:
        lines = schema_ddl.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if "-- @rows=" in line_lower:
                try:
                    # Use case-insensitive regex to match the check
                    import re

                    match = re.search(r"--\s*@rows\s*=\s*(\d+)", line, re.IGNORECASE)
                    if match:
                        row_count = int(match.group(1))
                        # Try to find table name on previous lines
                        for j in range(max(0, i - 5), i):
                            if "create table" in lines[j].lower():
                                # Extract table name case-insensitively
                                table_match = re.search(
                                    r"create\s+table\s+(\w+)", lines[j], re.IGNORECASE
                                )
                                if table_match:
                                    table_name = table_match.group(1).lower()
                                    # Check if this table exists (case-insensitive)
                                    for table_key in tables.keys():
                                        if table_key.lower() == table_name:
                                            row_hints[table_key] = row_count
                                            break
                                    break
                except (ValueError, IndexError):
                    pass

    return {"tables": tables, "row_hints": row_hints}
