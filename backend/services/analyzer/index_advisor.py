"""Index recommendation engine using AST traversal."""

from typing import Literal

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
    alias_to_table = query_ast.get_table_aliases()

    # Identify primary table (first table in FROM clause)
    primary_table = None
    if isinstance(query_ast.ast, expressions.Select):
        from_clause = query_ast.ast.find(expressions.From)
        if from_clause:
            table_expr = from_clause.find(expressions.Table)
            if table_expr:
                primary_table = table_expr.name

    for table in referenced_tables:
        table_suggestions = []

        def _get_table_cols(all_cols, target_table, is_join=False):
            cols = []
            for col in all_cols:
                if "." in col:
                    prefix, col_name = col.split(".", 1)
                    if alias_to_table.get(prefix) == target_table:
                        cols.append(col_name)
                else:
                    # Heuristic: if unqualified, assume it belongs to primary table
                    # or if it's a JOIN column, it likely belongs to all tables in the join
                    if target_table == primary_table or len(referenced_tables) == 1 or is_join:
                        cols.append(col)
            return cols

        table_where_cols = _get_table_cols(where_columns, table)
        table_join_cols = _get_table_cols(join_columns, table, is_join=True)
        table_order_cols = _get_table_cols(order_by_columns, table)
        table_group_cols = _get_table_cols(group_by_columns, table)


        # 1. Composite Index (WHERE + ORDER BY)
        if table_where_cols and table_order_cols:
            combined = list(dict.fromkeys(table_where_cols + table_order_cols))
            table_suggestions.append(
                IndexSuggestion(
                    table=table,
                    columns=combined[:4],
                    type="btree",
                    rationale=f"Composite index for WHERE filtering and ORDER BY on {', '.join(combined[:4])}",
                    expected_improvement="Avoids filesort and speeds up filtering",
                )
            )
        elif table_where_cols:
            table_suggestions.append(
                IndexSuggestion(
                    table=table,
                    columns=table_where_cols[:3],
                    type="btree",
                    rationale=f"Supports WHERE clause filtering on {', '.join(table_where_cols[:3])}",
                    expected_improvement="Faster predicate evaluation",
                )
            )

        # 2. JOIN columns (if not already covered)
        if table_join_cols:
            unique_join = list(dict.fromkeys(table_join_cols))
            if not any(set(unique_join[:1]).issubset(set(s.columns)) for s in table_suggestions):
                table_suggestions.append(
                    IndexSuggestion(
                        table=table,
                        columns=unique_join[:2],
                        type="btree",
                        rationale=f"Optimizes JOIN performance on {', '.join(unique_join[:2])}",
                        expected_improvement="Faster join execution",
                    )
                )

        # 3. ORDER BY (if not already covered)
        if table_order_cols and not any(set(table_order_cols[:1]).issubset(set(s.columns)) for s in table_suggestions):
            table_suggestions.append(
                IndexSuggestion(
                    table=table,
                    columns=table_order_cols[:2],
                    type="btree",
                    rationale=f"Improves ORDER BY performance on {', '.join(table_order_cols[:2])}",
                    expected_improvement="Avoids sort operation",
                )
            )

        # 4. GROUP BY
        if table_group_cols:
            table_suggestions.append(
                IndexSuggestion(
                    table=table,
                    columns=table_group_cols[:2],
                    type="btree",
                    rationale=f"Speeds up GROUP BY on {', '.join(table_group_cols[:2])}",
                    expected_improvement="Faster aggregation",
                )
            )

        # 5. LIKE patterns (GIN for PG)
        if dialect == "postgres":
            like_exprs = query_ast.get_like_expressions()
            for like_expr in like_exprs:
                col = like_expr.this
                if isinstance(col, expressions.Column):
                    col_table = col.table if col.table else None
                    col_name = col.name if col.name else None
                    
                    actual_table = None
                    if col_table:
                        actual_table = alias_to_table.get(col_table)
                    elif len(referenced_tables) == 1:
                        actual_table = list(referenced_tables)[0]
                    
                    if actual_table == table and col_name:
                        pattern = like_expr.expression
                        if isinstance(pattern, expressions.Literal):
                            pattern_str = str(pattern.this).strip("'\"")
                            if pattern_str.startswith("%"):
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
        key = (sug.table, tuple(sug.columns), sug.type)
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
        using_list = join.args.get("using")
        if using_list:
            for col in using_list:
                if isinstance(col, (expressions.Column, expressions.Identifier)):
                    table = col.table if hasattr(col, "table") else None
                    col_name = col.name if hasattr(col, "name") else str(col)
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
