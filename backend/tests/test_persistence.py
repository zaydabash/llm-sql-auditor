"""Tests for persistence module."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from backend.core.models import AuditResponse, Summary, Issue, IndexSuggestion
from backend.services.persistence import AuditHistory


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def audit_history(temp_db):
    """Create AuditHistory instance with temporary database."""
    return AuditHistory(db_path=temp_db)


@pytest.fixture
def sample_audit_response():
    """Create a sample AuditResponse for testing."""
    return AuditResponse(
        summary=Summary(
            total_issues=2,
            high_severity=1,
            est_improvement="2-3x speedup",
        ),
        issues=[
            Issue(
                code="R001",
                severity="warn",
                message="Avoid SELECT * in production queries",
                rule="SELECT_STAR",
            ),
            Issue(
                code="R004",
                severity="warn",
                message="Non-SARGable predicate detected",
                rule="NON_SARGABLE",
            ),
        ],
        rewrites=[],
        indexes=[
            IndexSuggestion(
                table="users",
                columns=["email"],
                type="btree",
                rationale="Supports WHERE clause",
            )
        ],
        llm_explain="Query has performance issues",
    )


def test_audit_history_init(temp_db):
    """Test AuditHistory initialization creates database."""
    history = AuditHistory(db_path=temp_db)
    assert os.path.exists(temp_db)


def test_save_audit(audit_history, sample_audit_response):
    """Test saving audit to history."""
    schema = "CREATE TABLE users (id INTEGER, email TEXT);"
    queries = ["SELECT * FROM users WHERE LOWER(email) = 'test@example.com';"]

    audit_id = audit_history.save_audit(
        schema_ddl=schema,
        queries=queries,
        dialect="postgres",
        response=sample_audit_response,
        user_id="test_user",
    )

    assert isinstance(audit_id, int)
    assert audit_id > 0


def test_get_audit(audit_history, sample_audit_response):
    """Test retrieving audit by ID."""
    schema = "CREATE TABLE users (id INTEGER, email TEXT);"
    queries = ["SELECT * FROM users;"]

    # Save audit
    audit_id = audit_history.save_audit(
        schema_ddl=schema,
        queries=queries,
        dialect="sqlite",
        response=sample_audit_response,
    )

    # Retrieve audit
    audit = audit_history.get_audit(audit_id)

    assert audit is not None
    assert audit["id"] == audit_id
    assert audit["schema_ddl"] == schema
    assert audit["queries"] == queries
    assert audit["dialect"] == "sqlite"
    assert "response" in audit
    assert audit["response"]["summary"]["total_issues"] == 2


def test_get_audit_not_found(audit_history):
    """Test retrieving non-existent audit."""
    audit = audit_history.get_audit(99999)
    assert audit is None


def test_list_recent_audits(audit_history, sample_audit_response):
    """Test listing recent audits."""
    schema = "CREATE TABLE users (id INTEGER);"

    # Save multiple audits
    for i in range(5):
        audit_history.save_audit(
            schema_ddl=schema,
            queries=[f"SELECT * FROM users WHERE id = {i};"],
            dialect="postgres",
            response=sample_audit_response,
            user_id=f"user_{i}",
        )

    # List recent audits
    audits = audit_history.list_recent_audits(limit=3)

    assert len(audits) == 3
    assert all("id" in audit for audit in audits)
    assert all("created_at" in audit for audit in audits)
    assert all("dialect" in audit for audit in audits)


def test_list_recent_audits_empty(audit_history):
    """Test listing audits when database is empty."""
    audits = audit_history.list_recent_audits()
    assert audits == []


def test_save_audit_with_complex_response(audit_history):
    """Test saving audit with complex response data."""
    schema = "CREATE TABLE orders (id INTEGER, user_id INTEGER, total DECIMAL);"
    queries = [
        "SELECT * FROM orders WHERE user_id = 1;",
        "SELECT COUNT(*) FROM orders;",
    ]

    response = AuditResponse(
        summary=Summary(
            total_issues=5,
            high_severity=2,
            est_improvement="5-10x speedup",
        ),
        issues=[
            Issue(code=f"R00{i}", severity="warn", message=f"Issue {i}", rule=f"RULE_{i}")
            for i in range(5)
        ],
        rewrites=[],
        indexes=[
            IndexSuggestion(
                table="orders",
                columns=["user_id", "created_at"],
                type="btree",
                rationale="Composite index for filtering",
            )
        ],
        llm_explain="Complex query optimization needed",
    )

    audit_id = audit_history.save_audit(
        schema_ddl=schema,
        queries=queries,
        dialect="postgres",
        response=response,
        user_id="power_user",
    )

    # Verify retrieval
    audit = audit_history.get_audit(audit_id)
    assert audit is not None
    assert len(audit["queries"]) == 2
    assert audit["response"]["summary"]["total_issues"] == 5


def test_audit_history_concurrent_saves(audit_history, sample_audit_response):
    """Test multiple concurrent saves."""
    schema = "CREATE TABLE test (id INTEGER);"
    audit_ids = []

    for i in range(10):
        audit_id = audit_history.save_audit(
            schema_ddl=schema,
            queries=[f"SELECT * FROM test WHERE id = {i};"],
            dialect="sqlite",
            response=sample_audit_response,
        )
        audit_ids.append(audit_id)

    # All IDs should be unique
    assert len(audit_ids) == len(set(audit_ids))

    # All should be retrievable
    for audit_id in audit_ids:
        audit = audit_history.get_audit(audit_id)
        assert audit is not None
