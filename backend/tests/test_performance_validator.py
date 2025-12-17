"""Tests for the performance validator."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.services.performance_validator import validate_index_suggestion, _generate_index_ddl, _analyze_explain_plans
from backend.core.models import IndexSuggestion


@pytest.mark.asyncio
async def test_validate_index_suggestion_no_conn():
    """Test validation when no connection string is provided."""
    suggestion = IndexSuggestion(table="t1", columns=["c1"], rationale="test")
    result = await validate_index_suggestion("SELECT * FROM t1", suggestion, "sqlite", None)
    assert result["validated"] is False
    assert "No database connection" in result["reason"]


@pytest.mark.asyncio
async def test_validate_index_suggestion_success():
    """Test successful index validation."""
    suggestion = IndexSuggestion(table="t1", columns=["c1"], rationale="test")
    
    with patch("backend.services.performance_validator.ExplainExecutor") as mock_executor_cls:
        mock_executor = MagicMock()
        mock_executor.execute_explain = AsyncMock(side_effect=["Plan Before", "Plan After"])
        mock_executor.execute_query_with_timing = AsyncMock(side_effect=[
            {"time_ms": 100.0},
            {"time_ms": 10.0}
        ])
        mock_executor.run_ddl = AsyncMock(return_value=(True, None))
        mock_executor_cls.return_value = mock_executor
        
        result = await validate_index_suggestion(
            "SELECT * FROM t1", suggestion, "sqlite", "sqlite:///:memory:"
        )
        
        assert result["validated"] is True
        assert result["speedup"] == 10.0
        assert result["timing_before_ms"] == 100.0
        assert result["timing_after_ms"] == 10.0


def test_generate_index_ddl():
    """Test index DDL generation."""
    suggestion = IndexSuggestion(table="users", columns=["email"], rationale="test")
    
    # SQLite
    ddl_sqlite = _generate_index_ddl(suggestion, "sqlite")
    assert "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)" in ddl_sqlite
    
    # Postgres
    ddl_pg = _generate_index_ddl(suggestion, "postgres")
    assert "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)" in ddl_pg
    
    # Postgres GIN
    suggestion_gin = IndexSuggestion(table="users", columns=["data"], rationale="test", type="gin")
    ddl_gin = _generate_index_ddl(suggestion_gin, "postgres")
    assert "USING gin" in ddl_gin


def test_analyze_explain_plans_postgres():
    """Test explain plan analysis for Postgres."""
    # Seq scan
    res = _analyze_explain_plans("Seq Scan on users", "Index Scan on users", "postgres")
    assert res["improvement"] == "likely"
    
    # Index scan already
    res = _analyze_explain_plans("Index Scan on users", "Index Scan on users", "postgres")
    assert res["improvement"] == "possible"


def test_analyze_explain_plans_sqlite():
    """Test explain plan analysis for SQLite."""
    # Scan table
    res = _analyze_explain_plans("SCAN TABLE users", "SEARCH TABLE users", "sqlite")
    assert res["improvement"] == "likely"
    
    # Search already
    res = _analyze_explain_plans("SEARCH TABLE users", "SEARCH TABLE users", "sqlite")
    assert res["improvement"] == "possible"
