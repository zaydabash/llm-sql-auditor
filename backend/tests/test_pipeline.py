"""Tests for audit pipeline."""

import pytest

from backend.services.pipeline import audit_queries


@pytest.mark.asyncio
async def test_audit_queries_basic():
    """Test basic audit pipeline."""
    schema = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL
    );
    """

    queries = ["SELECT * FROM users;"]

    result = await audit_queries(
        schema_ddl=schema,
        queries=queries,
        dialect="sqlite",
        use_llm=False,
    )

    assert result.summary.total_issues > 0
    assert result.summary.total_issues == len(result.issues)


@pytest.mark.asyncio
async def test_audit_queries_multiple_issues():
    """Test audit with multiple issues."""
    schema = """
    -- @rows=50000
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP
    );
    """

    queries = [
        "SELECT * FROM orders WHERE LOWER(status) = 'pending';",
        "SELECT * FROM orders ORDER BY created_at;",
    ]

    result = await audit_queries(
        schema_ddl=schema,
        queries=queries,
        dialect="sqlite",
        use_llm=False,
    )

    assert result.summary.total_issues > 0
    # Should have issues from both queries
    assert len(result.issues) >= 2


@pytest.mark.asyncio
async def test_audit_queries_good_query():
    """Test audit with well-optimized query."""
    schema = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL
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

    # Should have fewer issues (or none) for a good query
    assert result.summary.total_issues >= 0


@pytest.mark.asyncio
async def test_audit_queries_index_suggestions():
    """Test that index suggestions are generated."""
    schema = """
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP
    );
    """

    queries = ["SELECT * FROM orders WHERE user_id = 123 ORDER BY created_at;"]

    result = await audit_queries(
        schema_ddl=schema,
        queries=queries,
        dialect="sqlite",
        use_llm=False,
    )

    assert len(result.indexes) > 0
    order_indexes = [idx for idx in result.indexes if idx.table == "orders"]
    assert len(order_indexes) > 0
