"""Helpers for running EXPLAIN queries across different dialects."""

from typing import Literal


def get_explain_query(query: str, dialect: Literal["postgres", "sqlite"]) -> str:
    """
    Generate EXPLAIN query for a given SQL query.

    Args:
        query: Original SQL query
        dialect: SQL dialect

    Returns:
        EXPLAIN query string
    """
    if dialect == "postgres":
        return f"EXPLAIN ANALYZE {query}"
    elif dialect == "sqlite":
        return f"EXPLAIN QUERY PLAN {query}"
    else:
        return f"EXPLAIN {query}"


def format_explain_output(output: str, dialect: Literal["postgres", "sqlite"]) -> str:
    """Format EXPLAIN output for display."""
    # In a real implementation, would parse and format the explain output
    return output
