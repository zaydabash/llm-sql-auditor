"""Index recommendation engine using AST traversal."""

from typing import Literal

import sqlglot
from sqlglot import expressions

from backend.core.models import IndexSuggestion
from backend.services.analyzer.parser import QueryAST


def recommend_indexes(
    query_ast: QueryAST,
    table_info: dict,
    dialect: Literal["postgres", "sqlite"],
) -> list[IndexSuggestion]:
    """
    Recommend indexes based on query patterns using AST traversal.

    Returns list of IndexSuggestion objects.
    """
    suggestions = []

    # Extract columns using AST traversal
    where_columns = _extract_where_columns_ast(query_ast)
    join_columns = _extract_join_columns_ast(query_ast)
    order_by_columns = _extract_order_by_columns_ast(query_ast)
    group_by_columns = _extract_group_by_columns_ast(query_ast)

    referenced_tables = query_ast.get_referenced_tables()
    table_aliases = query_ast.get_table_aliases()

    # Create reverse mapping: alias -> table name
    alias_to_table = {alias: table for alias, table in table_aliases.items()}

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
        # Match columns by table name or alias
        table_join_cols = []
        for col in join_columns:
            if col.startswith(f"{table}."):
                table_join_cols.append(col)
            elif "." not in col:
                # Unqualified column - could belong to this table
                table_join_cols.append(col)
            else:
                # Check if it's an alias that maps to this table
                col_table = col.split(".")[0]
                # Resolve alias to actual table name
                actual_table = alias_to_table.get(col_table, col_table)
                if actual_table == table or col_table == table:
                    table_join_cols.append(col)
        
        if table_join_cols:
            # Deduplicate and extract column names
            unique_cols = list(set([col.split(".")[-1] for col in table_join_cols]))
            if unique_cols and not any(
                s.table == table and set(s.columns) == set(unique_cols[: len(s.columns)])
                for s in table_suggestions
            ):
                table_suggestions.append(
                    IndexSuggestion(
                        table=table,
                        columns=unique_cols[:2],
                        type="btree",
                        rationale=f"Supports JOIN on {', '.join(unique_cols[:2])}",
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
        like_exprs = query_ast.get_like_expressions()
        if dialect == "postgres" and like_exprs:
            # Check if LIKE is used with text columns
            for like_expr in like_exprs:
                if isinstance(like_expr, expressions.Like):
                    col = like_expr.this
                    if isinstance(col, expressions.Column):
                        table_name = col.table if col.table else None
                        col_name = col.name if col.name else None
                        if table_name == table and col_name:
                            # Check if pattern starts with wildcard (needs GIN)
                            pattern = like_expr.expression
                            if isinstance(pattern, expressions.Literal):
                                pattern_str = pattern.this
                                if isinstance(pattern_str, str) and pattern_str.startswith("%"):
                                    # Full-text search - suggest GIN index
                                    table_suggestions.append(
                                        IndexSuggestion(
                                            table=table,
                                            columns=[col_name],
                                            type="gin",
                                            rationale=f"Supports full-text search on {col_name}",
                                            expected_improvement="Faster text pattern matching",
                                        )
                                    )

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


def _extract_where_columns_ast(query_ast: QueryAST) -> list[str]:
    """Extract column names from WHERE clauses using AST."""
    columns = []
    where_clauses = query_ast.get_where_predicates()

    for where_clause in where_clauses:
        if not isinstance(where_clause, expressions.Where):
            continue

        # Traverse the WHERE expression tree
        condition = where_clause.this
        _extract_columns_from_expression(condition, columns)

    return columns


def _extract_join_columns_ast(query_ast: QueryAST) -> list[str]:
    """Extract column names from JOIN conditions using AST."""
    columns = []
    joins = query_ast.get_joins()

    for join in joins:
        if not isinstance(join, expressions.Join):
            continue

        # Extract columns from JOIN condition
        # The join condition is stored in the join's expression tree
        # Find all binary operations (EQ, And, Or) that represent join conditions
        # These are typically at the top level of the join's expression tree
        
        # Look for equality expressions (EQ) which are common in JOIN ON clauses
        eq_exprs = list(join.find_all(expressions.EQ))
        for eq_expr in eq_exprs:
            _extract_columns_from_expression(eq_expr, columns)
        
        # Also check for other binary operations that might be join conditions
        # Look for columns directly in the join expression tree
        join_cols = list(join.find_all(expressions.Column))
        for col in join_cols:
            table = col.table if col.table else None
            col_name = col.name if col.name else None
            if col_name:
                columns.append(f"{table}.{col_name}" if table else col_name)

        # Check for USING clause
        if hasattr(join, "using") and join.using:
            using_cols = join.using if isinstance(join.using, list) else [join.using]
            for col in using_cols:
                if isinstance(col, expressions.Column):
                    table = col.table if col.table else None
                    col_name = col.name if col.name else None
                    if col_name:
                        columns.append(f"{table}.{col_name}" if table else col_name)

    return columns


def _extract_order_by_columns_ast(query_ast: QueryAST) -> list[str]:
    """Extract column names from ORDER BY using AST."""
    columns = []
    order_clauses = query_ast.get_order_by()

    for order_clause in order_clauses:
        if not isinstance(order_clause, expressions.Order):
            continue

        for expr in order_clause.expressions:
            if isinstance(expr, expressions.Ordered):
                expr = expr.this

            if isinstance(expr, expressions.Column):
                table = expr.table if expr.table else None
                col_name = expr.name if expr.name else None
                if col_name:
                    columns.append(f"{table}.{col_name}" if table else col_name)
            elif isinstance(expr, expressions.Identifier):
                columns.append(expr.name)

    return columns


def _extract_group_by_columns_ast(query_ast: QueryAST) -> list[str]:
    """Extract column names from GROUP BY using AST."""
    columns = []
    ast = query_ast.ast

    # Find GROUP BY expressions
    group_by_exprs = ast.find_all(expressions.Group)

    for group_expr in group_by_exprs:
        if isinstance(group_expr, expressions.Group):
            for expr in group_expr.expressions:
                if isinstance(expr, expressions.Column):
                    table = expr.table if expr.table else None
                    col_name = expr.name if expr.name else None
                    if col_name:
                        columns.append(f"{table}.{col_name}" if table else col_name)
                elif isinstance(expr, expressions.Identifier):
                    columns.append(expr.name)

    return columns


def _extract_columns_from_expression(expr, columns: list[str]) -> None:
    """Recursively extract column references from an expression."""
    if expr is None:
        return

    # Base case: Column reference
    if isinstance(expr, expressions.Column):
        table = expr.table if expr.table else None
        col_name = expr.name if expr.name else None
        if col_name:
            columns.append(f"{table}.{col_name}" if table else col_name)
        return

    # Skip literals - they're not columns
    if isinstance(expr, expressions.Literal):
        return

    # Handle binary operations (AND, OR, =, <, >, etc.)
    # SQLGlot uses specific classes like Equals, And, Or, etc.
    # They all have 'this' and 'expression' attributes
    if hasattr(expr, "this") and hasattr(expr, "expression"):
        # This is likely a binary operation
        _extract_columns_from_expression(expr.this, columns)
        _extract_columns_from_expression(expr.expression, columns)
        return

    # Handle IN expressions
    if isinstance(expr, expressions.In):
        _extract_columns_from_expression(expr.this, columns)
        if hasattr(expr, "expressions") and expr.expressions:
            for e in expr.expressions:
                _extract_columns_from_expression(e, columns)
        return

    # Handle BETWEEN expressions
    if isinstance(expr, expressions.Between):
        _extract_columns_from_expression(expr.this, columns)
        if hasattr(expr, "low"):
            _extract_columns_from_expression(expr.low, columns)
        if hasattr(expr, "high"):
            _extract_columns_from_expression(expr.high, columns)
        return

    # Handle LIKE expressions
    if isinstance(expr, expressions.Like):
        _extract_columns_from_expression(expr.this, columns)
        return

    # Handle function calls (AggFunc, Func, etc.)
    if isinstance(expr, (expressions.AggFunc, expressions.Func)):
        # For index recommendations, we want the column inside functions
        if hasattr(expr, "expressions") and expr.expressions:
            for arg in expr.expressions:
                _extract_columns_from_expression(arg, columns)
        elif hasattr(expr, "this"):
            _extract_columns_from_expression(expr.this, columns)
        return

    # Handle subqueries
    if isinstance(expr, expressions.Subquery):
        if hasattr(expr, "this") and expr.this:
            _extract_columns_from_expression(expr.this, columns)
        return

    # Handle EXISTS
    if isinstance(expr, expressions.Exists):
        if hasattr(expr, "this") and expr.this:
            _extract_columns_from_expression(expr.this, columns)
        return

    # Handle other expression types recursively
    if hasattr(expr, "this"):
        _extract_columns_from_expression(expr.this, columns)
    if hasattr(expr, "expression"):
        _extract_columns_from_expression(expr.expression, columns)
    if hasattr(expr, "expressions"):
        for e in expr.expressions:
            _extract_columns_from_expression(e, columns)
