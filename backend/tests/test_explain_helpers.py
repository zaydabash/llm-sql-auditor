"""Tests for EXPLAIN helpers."""

import pytest
from backend.db.explain_helpers import get_explain_query, format_explain_output


def test_get_explain_query_postgres():
    """Test get_explain_query for PostgreSQL."""
    query = "SELECT * FROM users"
    result = get_explain_query(query, "postgres")
    assert result == "EXPLAIN ANALYZE SELECT * FROM users"


def test_get_explain_query_sqlite():
    """Test get_explain_query for SQLite."""
    query = "SELECT * FROM users"
    result = get_explain_query(query, "sqlite")
    assert result == "EXPLAIN QUERY PLAN SELECT * FROM users"


def test_get_explain_query_other():
    """Test get_explain_query for other dialects."""
    query = "SELECT * FROM users"
    # Using type ignore because Literal only allows postgres/sqlite but code handles others
    result = get_explain_query(query, "mysql")  # type: ignore
    assert result == "EXPLAIN SELECT * FROM users"


def test_format_explain_output():
    """Test format_explain_output."""
    output = "Some explain output"
    assert format_explain_output(output, "postgres") == output
    assert format_explain_output(output, "sqlite") == output
