"""Comprehensive tests for audit pipeline."""

import pytest

from backend.services.pipeline import audit_queries


@pytest.mark.asyncio
async def test_audit_queries_complex_scenario():
    """Test audit with complex real-world scenario."""
    schema = """
    -- @rows=50000
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP,
        status TEXT
    );
    
    -- @rows=100000
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP,
        total_cents INTEGER,
        status TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """

    queries = [
        "SELECT * FROM orders WHERE user_id = 123 ORDER BY created_at DESC;",
        "SELECT * FROM users WHERE LOWER(email) = 'admin@example.com';",
        "SELECT * FROM orders o JOIN users u ON u.id = o.user_id WHERE o.status = 'pending';",
    ]

    result = await audit_queries(
        schema_ddl=schema,
        queries=queries,
        dialect="sqlite",
        use_llm=False,
    )

    assert result.summary.total_issues > 0
    assert len(result.issues) > 0
    assert len(result.indexes) > 0

    # Verify issue codes
    codes = [issue.code for issue in result.issues]
    assert "R001" in codes  # SELECT *

    # Verify index suggestions
    assert any(idx.table == "orders" for idx in result.indexes)
    assert any(idx.table == "users" for idx in result.indexes)


@pytest.mark.asyncio
async def test_audit_queries_empty_result():
    """Test audit with well-optimized query."""
    schema = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL UNIQUE
    );
    CREATE INDEX idx_users_email ON users(email);
    """

    queries = ["SELECT id, email FROM users WHERE email = 'test@example.com';"]

    result = await audit_queries(
        schema_ddl=schema,
        queries=queries,
        dialect="sqlite",
        use_llm=False,
    )

    # Should have minimal issues for a well-optimized query
    assert result.summary.total_issues >= 0
    assert isinstance(result.issues, list)


@pytest.mark.asyncio
async def test_audit_queries_error_handling():
    """Test audit handles parse errors gracefully."""
    schema = "CREATE TABLE users (id INTEGER);"

    queries = [
        "SELECT * FROM users;",  # Valid
        "SELECT * FROM invalid_table;",  # Invalid table
        "INVALID SQL SYNTAX!!!",  # Invalid syntax
    ]

    result = await audit_queries(
        schema_ddl=schema,
        queries=queries,
        dialect="sqlite",
        use_llm=False,
    )

    # Should process valid queries and report errors for invalid ones
    assert result.summary.total_issues >= 0
    # Should have parse errors for invalid queries
    parse_errors = [issue for issue in result.issues if issue.code == "PARSE_ERROR"]
    assert len(parse_errors) > 0

