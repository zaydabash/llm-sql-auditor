"""Rules engine for detecting SQL issues."""

import re

from backend.core.models import Issue
from backend.services.analyzer.parser import QueryAST


def check_select_star(query_ast: QueryAST, query_index: int) -> list[Issue]:
    """R001: Detect SELECT * usage."""
    issues = []
    stars = query_ast.get_select_star()
    if stars:
        issues.append(
            Issue(
                code="R001",
                severity="warn",
                message="Avoid SELECT * in production queries. Specify columns explicitly to reduce data transfer and improve maintainability.",
                snippet=query_ast.query[:200],
                rule="SELECT_STAR",
                query_index=query_index,
            )
        )
    return issues


def check_unused_join(query_ast: QueryAST, query_index: int) -> list[Issue]:
    """R002: Detect joins where columns aren't referenced."""
    issues = []
    joins = query_ast.get_joins()
    referenced_columns = query_ast.get_referenced_columns()

    for join in joins:
        if isinstance(join, dict) or not hasattr(join, "this"):
            continue

        join_table = None
        if hasattr(join, "this") and hasattr(join.this, "name"):
            join_table = join.this.name

        if join_table:
            # Check if any columns from this table are referenced
            table_columns_referenced = any(
                col.startswith(f"{join_table}.") or col == join_table for col in referenced_columns
            )
            if not table_columns_referenced:
                issues.append(
                    Issue(
                        code="R002",
                        severity="warn",
                        message=f"Join on table '{join_table}' appears unused - no columns from this table are referenced in SELECT or WHERE clauses.",
                        snippet=query_ast.query[:200],
                        rule="UNUSED_JOIN",
                        query_index=query_index,
                    )
                )
    return issues


def check_cartesian_join(query_ast: QueryAST, query_index: int) -> list[Issue]:
    """R003: Detect joins without ON predicate (cartesian products)."""
    issues = []
    joins = query_ast.get_joins()

    for join in joins:
        # Check if join has ON clause
        has_on = False
        if hasattr(join, "expressions"):
            for expr in join.expressions:
                if hasattr(expr, "this") and str(expr.this).upper() == "ON":
                    has_on = True
                    break

        # Also check for join conditions in the join object itself
        if not has_on and not hasattr(join, "on"):
            issues.append(
                Issue(
                    code="R003",
                    severity="error",
                    message="Join without ON predicate creates a cartesian product. This can cause severe performance issues.",
                    snippet=query_ast.query[:200],
                    rule="CARTESIAN_JOIN",
                    query_index=query_index,
                )
            )
    return issues


def check_non_sargable(query_ast: QueryAST, query_index: int) -> list[Issue]:
    """R004: Detect functions on indexed columns in WHERE (non-SARGable predicates)."""
    issues = []
    _ = query_ast.get_where_predicates()  # Check WHERE exists, but use regex for pattern matching

    # Common non-SARGable patterns
    non_sargable_patterns = [
        r"LOWER\s*\(",
        r"UPPER\s*\(",
        r"TRIM\s*\(",
        r"SUBSTRING\s*\(",
        r"SUBSTR\s*\(",
        r"CAST\s*\(",
        r"::\s*\w+",  # PostgreSQL casting
        r"DATE\s*\(",
        r"YEAR\s*\(",
        r"MONTH\s*\(",
    ]

    query_upper = query_ast.query.upper()
    for pattern in non_sargable_patterns:
        if re.search(pattern, query_upper):
            issues.append(
                Issue(
                    code="R004",
                    severity="warn",
                    message="Function applied to column in WHERE clause prevents index usage. Consider rewriting to apply function to the constant instead.",
                    snippet=query_ast.query[:200],
                    rule="NON_SARGABLE",
                    query_index=query_index,
                )
            )
            break  # Only report once per query

    return issues


def check_missing_predicate(query_ast: QueryAST, query_index: int, table_info: dict) -> list[Issue]:
    """R005: Detect large table scans without WHERE limiters."""
    issues = []
    where_clauses = query_ast.get_where_predicates()
    referenced_tables = query_ast.get_referenced_tables()

    # If no WHERE clause and referencing tables with row hints
    if not where_clauses:
        for table in referenced_tables:
            row_hints = table_info.get("row_hints", {})
            if table in row_hints and row_hints[table] > 10000:
                issues.append(
                    Issue(
                        code="R005",
                        severity="warn",
                        message=f"Query scans large table '{table}' without WHERE clause. Consider adding filters to limit result set.",
                        snippet=query_ast.query[:200],
                        rule="MISSING_PREDICATE",
                        query_index=query_index,
                    )
                )

    return issues


def check_order_by_no_index(query_ast: QueryAST, query_index: int) -> list[Issue]:
    """R006: ORDER BY columns lacking supporting index."""
    issues = []
    order_by_clauses = query_ast.get_order_by()

    if order_by_clauses:
        issues.append(
            Issue(
                code="R006",
                severity="info",
                message="ORDER BY may benefit from an index on the sorted columns. Consider adding a covering index.",
                snippet=query_ast.query[:200],
                rule="ORDER_BY_NO_INDEX",
                query_index=query_index,
            )
        )

    return issues


def check_distinct_misuse(query_ast: QueryAST, query_index: int) -> list[Issue]:
    """R007: DISTINCT as de-dupe band-aid."""
    issues = []
    distinct_clauses = query_ast.get_distinct()
    joins = query_ast.get_joins()

    # If DISTINCT is used with joins, it might be masking duplicates from join issues
    if distinct_clauses and joins:
        issues.append(
            Issue(
                code="R007",
                severity="info",
                message="DISTINCT used with joins may indicate duplicate rows from join conditions. Review join predicates.",
                snippet=query_ast.query[:200],
                rule="DISTINCT_MISUSE",
                query_index=query_index,
            )
        )

    return issues


def check_n_plus_one(query_ast: QueryAST, query_index: int) -> list[Issue]:
    """R008: N+1 pattern - repeated subqueries with correlated predicates."""
    issues = []
    _ = query_ast.get_subqueries()  # Check subqueries exist, but use regex for pattern matching

    # Look for correlated subqueries (simplified check)
    query_lower = query_ast.query.lower()
    # Pattern: subquery that references outer table
    if "exists" in query_lower or "in (" in query_lower:
        # Check for correlation (simplified)
        if re.search(r"\.\w+\s*[=<>]", query_ast.query):
            issues.append(
                Issue(
                    code="R008",
                    severity="warn",
                    message="Correlated subquery detected. Consider rewriting as JOIN for better performance.",
                    snippet=query_ast.query[:200],
                    rule="N_PLUS_ONE_PATTERN",
                    query_index=query_index,
                )
            )

    return issues


def check_like_prefix_wildcard(query_ast: QueryAST, query_index: int) -> list[Issue]:
    """R009: LIKE with prefix wildcard blocks index usage."""
    issues = []
    like_exprs = query_ast.get_like_expressions()

    if like_exprs:
        query_lower = query_ast.query.lower()
        # Check for LIKE '%...' or LIKE '%...%' patterns
        if re.search(r"like\s+['\"]%", query_lower) or re.search(
            r"like\s+['\"][^'\"]*%[^'\"]*['\"]", query_lower
        ):
            issues.append(
                Issue(
                    code="R009",
                    severity="warn",
                    message="LIKE pattern with leading wildcard prevents index usage. Consider full-text search or restructuring the query.",
                    snippet=query_ast.query[:200],
                    rule="LIKE_PREFIX_WILDCARD",
                    query_index=query_index,
                )
            )

    return issues


def check_agg_no_grouping_index(query_ast: QueryAST, query_index: int) -> list[Issue]:
    """R010: Heavy aggregations missing covering indexes."""
    issues = []
    aggregations = query_ast.get_aggregations()

    if aggregations:
        issues.append(
            Issue(
                code="R010",
                severity="info",
                message="Aggregation query may benefit from a covering index on GROUP BY and aggregated columns.",
                snippet=query_ast.query[:200],
                rule="AGG_NO_GROUPING_INDEX",
                query_index=query_index,
            )
        )

    return issues


def run_all_rules(query_ast: QueryAST, query_index: int, table_info: dict) -> list[Issue]:
    """Run all rules and return combined issues."""
    all_issues = []

    all_issues.extend(check_select_star(query_ast, query_index))
    all_issues.extend(check_unused_join(query_ast, query_index))
    all_issues.extend(check_cartesian_join(query_ast, query_index))
    all_issues.extend(check_non_sargable(query_ast, query_index))
    all_issues.extend(check_missing_predicate(query_ast, query_index, table_info))
    all_issues.extend(check_order_by_no_index(query_ast, query_index))
    all_issues.extend(check_distinct_misuse(query_ast, query_index))
    all_issues.extend(check_n_plus_one(query_ast, query_index))
    all_issues.extend(check_like_prefix_wildcard(query_ast, query_index))
    all_issues.extend(check_agg_no_grouping_index(query_ast, query_index))

    return all_issues
