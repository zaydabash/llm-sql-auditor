"""Index recommendation engine."""

import re
from typing import Literal

from backend.core.models import IndexSuggestion
from backend.services.analyzer.parser import QueryAST


def recommend_indexes(
    query_ast: QueryAST,
    table_info: dict,
    dialect: Literal["postgres", "sqlite"],
) -> list[IndexSuggestion]:
    """
    Recommend indexes based on query patterns.

    Returns list of IndexSuggestion objects.
    """
    suggestions = []

    # Extract WHERE clause columns
    where_columns = _extract_where_columns(query_ast)
    # Extract JOIN columns
    join_columns = _extract_join_columns(query_ast)
    # Extract ORDER BY columns
    order_by_columns = _extract_order_by_columns(query_ast)
    # Extract GROUP BY columns
    group_by_columns = _extract_group_by_columns(query_ast)

    referenced_tables = query_ast.get_referenced_tables()

    for table in referenced_tables:
        table_suggestions = []

        # Check for WHERE predicates
        table_where_cols = [
            col for col in where_columns if col.startswith(f"{table}.") or "." not in col
        ]
        if table_where_cols:
            cols = [col.split(".")[-1] for col in table_where_cols]
            if cols:
                table_suggestions.append(
                    IndexSuggestion(
                        table=table,
                        columns=cols[:3],  # Limit to 3 columns for composite index
                        type="btree",
                        rationale=f"Supports WHERE clause filtering on {', '.join(cols[:3])}",
                        expected_improvement="Faster predicate evaluation",
                    )
                )

        # Check for JOIN keys
        table_join_cols = [
            col for col in join_columns if col.startswith(f"{table}.") or "." not in col
        ]
        if table_join_cols:
            cols = [col.split(".")[-1] for col in table_join_cols]
            if cols and not any(
                s.table == table and s.columns == cols[: len(s.columns)]
                for s in table_suggestions
            ):
                table_suggestions.append(
                    IndexSuggestion(
                        table=table,
                        columns=cols[:2],
                        type="btree",
                        rationale=f"Supports JOIN on {', '.join(cols[:2])}",
                        expected_improvement="Faster join operations",
                    )
                )

        # Check for ORDER BY
        table_order_cols = [
            col for col in order_by_columns if col.startswith(f"{table}.") or "." not in col
        ]
        if table_order_cols:
            cols = [col.split(".")[-1] for col in table_order_cols]
            if cols:
                # Check if we already have a WHERE index we can extend
                existing = next(
                    (
                        s
                        for s in table_suggestions
                        if s.table == table and s.type == "btree"
                    ),
                    None,
                )
                if existing:
                    # Extend existing index
                    combined = list(existing.columns) + [c for c in cols if c not in existing.columns]
                    existing.columns = combined[:4]  # Limit composite index size
                    existing.rationale += f" and ORDER BY on {', '.join(cols)}"
                else:
                    table_suggestions.append(
                        IndexSuggestion(
                            table=table,
                            columns=cols[:3],
                            type="btree",
                            rationale=f"Supports ORDER BY on {', '.join(cols[:3])}",
                            expected_improvement="Faster sorting without filesort",
                        )
                    )

        # Check for GROUP BY
        table_group_cols = [
            col for col in group_by_columns if col.startswith(f"{table}.") or "." not in col
        ]
        if table_group_cols:
            cols = [col.split(".")[-1] for col in table_group_cols]
            if cols:
                table_suggestions.append(
                    IndexSuggestion(
                        table=table,
                        columns=cols[:3],
                        type="btree",
                        rationale=f"Supports GROUP BY aggregation on {', '.join(cols[:3])}",
                        expected_improvement="Faster grouping operations",
                    )
                )

        # Check for LIKE patterns (suggest GIN for full-text in PG)
        query_lower = query_ast.query.lower()
        if dialect == "postgres" and "like" in query_lower:
            # This is simplified - in practice would check for text search patterns
            pass

        suggestions.extend(table_suggestions)

    # Deduplicate suggestions
    seen = set()
    unique_suggestions = []
    for sug in suggestions:
        key = (sug.table, tuple(sug.columns))
        if key not in seen:
            seen.add(key)
            unique_suggestions.append(sug)

    return unique_suggestions


def _extract_where_columns(query_ast: QueryAST) -> list[str]:
    """Extract column names from WHERE clauses."""
    columns = []
    query = query_ast.query

    # Simple regex-based extraction (in production, use AST)
    # Pattern: column_name =, column_name >, etc.
    patterns = [
        r"(\w+)\.(\w+)\s*[=<>]",
        r"(\w+)\s*[=<>]",
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, query, re.IGNORECASE)
        for match in matches:
            if len(match.groups()) == 2:
                columns.append(f"{match.group(1)}.{match.group(2)}")
            else:
                columns.append(match.group(1))

    return columns


def _extract_join_columns(query_ast: QueryAST) -> list[str]:
    """Extract column names from JOIN conditions."""
    columns = []
    query = query_ast.query

    # Pattern: table1.col1 = table2.col2
    pattern = r"(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)"
    matches = re.finditer(pattern, query, re.IGNORECASE)
    for match in matches:
        columns.append(f"{match.group(1)}.{match.group(2)}")
        columns.append(f"{match.group(3)}.{match.group(4)}")

    return columns


def _extract_order_by_columns(query_ast: QueryAST) -> list[str]:
    """Extract column names from ORDER BY."""
    columns = []
    query = query_ast.query

    if "ORDER BY" in query.upper():
        # Extract ORDER BY clause - match case-insensitive
        # Match until semicolon, LIMIT, or end of string
        order_match = re.search(
            r"ORDER\s+BY\s+([^;]+?)(?:\s+LIMIT|\s*;|$)", query, re.IGNORECASE | re.DOTALL
        )
        if order_match:
            order_clause = order_match.group(1).strip()
            # Remove DESC/ASC keywords
            order_clause = re.sub(r'\s+(DESC|ASC)\b', '', order_clause, flags=re.IGNORECASE)
            order_clause = order_clause.strip()
            # Extract column names - handle both table.col and just col
            # Match word characters, optionally followed by .word
            col_pattern = r'\b(\w+)(?:\.(\w+))?\b'
            col_matches = re.finditer(col_pattern, order_clause)
            for match in col_matches:
                col_name = match.group(2) if match.group(2) else match.group(1)
                table_name = match.group(1) if match.group(2) else None
                # Skip keywords
                if col_name.upper() not in ['DESC', 'ASC', 'NULLS', 'FIRST', 'LAST']:
                    if table_name and match.group(2):
                        columns.append(f"{table_name}.{col_name}")
                    else:
                        columns.append(col_name)

    return columns


def _extract_group_by_columns(query_ast: QueryAST) -> list[str]:
    """Extract column names from GROUP BY."""
    columns = []
    query = query_ast.query

    if "GROUP BY" in query.upper():
        group_match = re.search(
            r"GROUP\s+BY\s+([^;]+?)(?:\s+ORDER|\s+HAVING|\s*;|$)",
            query,
            re.IGNORECASE | re.DOTALL,
        )
        if group_match:
            group_clause = group_match.group(1).strip()
            # Extract column names - handle both table.col and just col
            col_pattern = r'\b(\w+)(?:\.(\w+))?\b'
            col_matches = re.finditer(col_pattern, group_clause)
            for match in col_matches:
                col_name = match.group(2) if match.group(2) else match.group(1)
                table_name = match.group(1) if match.group(2) else None
                # Skip SQL keywords
                if col_name.upper() not in ['BY', 'HAVING', 'ORDER']:
                    if table_name and match.group(2):
                        columns.append(f"{table_name}.{col_name}")
                    else:
                        columns.append(col_name)

    return columns

