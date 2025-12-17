"""Tests for performance_validator module."""

import pytest
from backend.core.models import IndexSuggestion
from backend.services.performance_validator import (
    _analyze_explain_plans,
    _generate_index_ddl,
    validate_index_suggestion,
)


def test_generate_index_ddl_postgres():
    """Test PostgreSQL index DDL generation."""
    index = IndexSuggestion(
        table="users",
        columns=["email", "created_at"],
        type="btree",
        rationale="Supports WHERE and ORDER BY",
    )

    ddl = _generate_index_ddl(index, "postgres")
    assert "CREATE INDEX IF NOT EXISTS" in ddl
    assert "idx_users_email_created_at" in ddl
    assert "ON users (email, created_at)" in ddl


def test_generate_index_ddl_postgres_gin():
    """Test PostgreSQL GIN index DDL generation."""
    index = IndexSuggestion(
        table="documents",
        columns=["content"],
        type="gin",
        rationale="Full-text search",
    )

    ddl = _generate_index_ddl(index, "postgres")
    assert "USING gin" in ddl
    assert "idx_documents_content" in ddl


def test_generate_index_ddl_sqlite():
    """Test SQLite index DDL generation."""
    index = IndexSuggestion(
        table="orders",
        columns=["user_id", "status"],
        type="btree",
        rationale="Supports JOIN and WHERE",
    )

    ddl = _generate_index_ddl(index, "sqlite")
    assert "CREATE INDEX IF NOT EXISTS" in ddl
    assert "idx_orders_user_id_status" in ddl
    assert "ON orders (user_id, status)" in ddl


def test_analyze_explain_plans_no_plan():
    """Test analysis when no EXPLAIN plan is available."""
    result = _analyze_explain_plans(None, None, "postgres")
    assert result["improvement"] == "unknown"
    assert "Could not get EXPLAIN plan" in result["reason"]


def test_analyze_explain_plans_postgres_seq_scan():
    """Test PostgreSQL plan analysis with sequential scan."""
    plan = """
    Seq Scan on users  (cost=0.00..10.00 rows=100 width=32)
      Filter: (email = 'test@example.com')
    """

    result = _analyze_explain_plans(plan, None, "postgres")
    assert result["improvement"] == "likely"
    assert "sequential scan" in result["reason"].lower()


def test_analyze_explain_plans_postgres_index_scan():
    """Test PostgreSQL plan analysis with index scan."""
    plan = """
    Index Scan using idx_users_email on users  (cost=0.00..8.27 rows=1 width=32)
      Index Cond: (email = 'test@example.com')
    """

    result = _analyze_explain_plans(plan, None, "postgres")
    assert result["improvement"] == "possible"
    assert "already uses indexes" in result["reason"]


def test_analyze_explain_plans_sqlite_table_scan():
    """Test SQLite plan analysis with table scan."""
    plan = "SCAN TABLE users"

    result = _analyze_explain_plans(plan, None, "sqlite")
    assert result["improvement"] == "likely"
    assert "scans table" in result["reason"]


def test_analyze_explain_plans_sqlite_search():
    """Test SQLite plan analysis with search."""
    plan = "SEARCH TABLE users USING INDEX idx_users_email (email=?)"

    result = _analyze_explain_plans(plan, None, "sqlite")
    assert result["improvement"] == "possible"
    assert "uses search" in result["reason"]


@pytest.mark.asyncio
async def test_validate_index_suggestion_no_connection():
    """Test validation when no database connection is provided."""
    index = IndexSuggestion(
        table="users",
        columns=["email"],
        type="btree",
        rationale="Test",
    )

    result = await validate_index_suggestion(
        query="SELECT * FROM users WHERE email = 'test@example.com'",
        index_suggestion=index,
        dialect="postgres",
        connection_string=None,
    )

    assert result["validated"] is False
    assert "No database connection" in result["reason"]
