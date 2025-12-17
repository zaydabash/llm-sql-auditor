"""Heuristic cost estimation for SQL queries."""

from typing import Literal

from backend.services.analyzer.parser import QueryAST


def estimate_cost(
    query_ast: QueryAST, table_info: dict, dialect: Literal["postgres", "sqlite"]
) -> tuple[int, str]:
    """
    Estimate relative cost score (0-100) and improvement suggestion.

    Returns:
        (score, improvement_text) where score is 0-100 (higher = more expensive)
    """
    score = 0
    factors = []

    # Factor 1: Full table scans
    where_clauses = query_ast.get_where_predicates()
    referenced_tables = query_ast.get_referenced_tables()
    row_hints = table_info.get("row_hints", {})

    has_where = bool(where_clauses)
    if not has_where:
        for table in referenced_tables:
            rows = row_hints.get(table, 0)
            if rows > 100000:
                score += 50
                factors.append(f"Full scan on large table '{table}' ({rows:,} rows)")
            elif rows > 10000:
                score += 30
                factors.append(f"Full scan on table '{table}' ({rows:,} rows)")
            else:
                score += 15
                factors.append(f"Full scan on table '{table}'")

    # Factor 2: Non-SARGable predicates
    query_upper = query_ast.query.upper()
    if "LOWER(" in query_upper or "UPPER(" in query_upper:
        score += 25
        factors.append("Non-SARGable function in WHERE clause")

    # Factor 3: Cartesian joins
    joins = query_ast.get_joins()
    if joins:
        if "CROSS JOIN" in query_upper or not any(
            "ON" in str(j).upper() for j in joins if hasattr(j, "__str__")
        ):
            score += 40
            factors.append("Potential cartesian product")

    # Factor 4: Correlated subqueries
    if "EXISTS" in query_upper or ("IN (" in query_upper and "." in query_ast.query):
        score += 30
        factors.append("Correlated subquery detected")

    # Factor 5: LIKE with leading wildcard
    if "LIKE '%" in query_upper or 'LIKE "%' in query_upper:
        score += 20
        factors.append("LIKE with leading wildcard")

    # Factor 6: SELECT *
    if "*" in query_ast.query and "SELECT" in query_upper:
        score += 10
        factors.append("SELECT * increases data transfer")

    # Factor 7: Large OFFSET
    if "OFFSET" in query_upper:
        score += 15
        factors.append("Large OFFSET detected")

    # Cap score at 100
    score = min(100, score)

    # Generate improvement suggestion
    if score < 15:
        improvement = "Query looks well-optimized"
    elif score < 35:
        improvement = "Minor optimizations possible (1.2-2x speedup)"
    elif score < 55:
        improvement = "Moderate improvements available (2-4x speedup)"
    elif score < 75:
        improvement = "Significant optimization opportunities (4-10x speedup)"
    else:
        improvement = "Major performance issues detected (10x+ speedup possible)"


    if factors:
        improvement += f" - Issues: {', '.join(factors[:3])}"

    return score, improvement
