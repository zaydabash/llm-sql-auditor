"""Tests for the persistence layer."""

import os
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

try:
    import asyncpg
except ImportError:
    asyncpg = None

from backend.services.persistence import SQLitePersistence, PostgresPersistence, get_persistence

from backend.core.models import AuditResponse, Summary
from backend.core.config import settings


@pytest.fixture
def db_path(tmp_path):
    """Fixture for temporary database path."""
    return str(tmp_path / "test_audit_history.sqlite")


@pytest.mark.asyncio
async def test_sqlite_persistence_init(db_path):
    """Test SQLite database initialization."""
    persistence = SQLitePersistence(db_path)
    assert os.path.exists(db_path)


@pytest.mark.asyncio
async def test_sqlite_save_and_get_audit(db_path):
    """Test saving and retrieving an audit with SQLite."""
    persistence = SQLitePersistence(db_path)
    
    response = AuditResponse(
        summary=Summary(total_issues=1, high_severity=0, est_improvement="None"),
        issues=[],
        rewrites=[],
        indexes=[],
        llm_explain="Test"
    )
    
    audit_id = await persistence.save_audit(
        schema_ddl="CREATE TABLE t1 (id INT);",
        queries=["SELECT * FROM t1;"],
        dialect="sqlite",
        response=response,
        user_id="user1"
    )
    
    assert audit_id > 0
    
    retrieved = await persistence.get_audit(audit_id)
    assert retrieved is not None
    assert retrieved["dialect"] == "sqlite"
    assert retrieved["user_id"] == "user1"
    assert retrieved["response"]["llm_explain"] == "Test"


@pytest.mark.asyncio
async def test_sqlite_list_recent_audits(db_path):
    """Test listing recent audits with SQLite."""
    persistence = SQLitePersistence(db_path)
    
    response = AuditResponse(
        summary=Summary(total_issues=0, high_severity=0),
        issues=[],
        rewrites=[],
        indexes=[]
    )
    
    for i in range(5):
        await persistence.save_audit("SCHEMA", ["QUERY"], "sqlite", response)
        
    recent = await persistence.list_recent_audits(limit=3)
    assert len(recent) == 3
    assert recent[0]["id"] > recent[1]["id"]


@pytest.mark.asyncio
@pytest.mark.skipif(asyncpg is None, reason="asyncpg not installed")
async def test_postgres_persistence_mock():
    """Test PostgresPersistence with mocked asyncpg."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool
        
        persistence = PostgresPersistence("postgresql://user:pass@localhost/db")
        
        # Test save_audit
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetchrow.return_value = {"id": 123}
        
        response = AuditResponse(
            summary=Summary(total_issues=0, high_severity=0),
            issues=[],
            rewrites=[],
            indexes=[]
        )
        
        audit_id = await persistence.save_audit("SCHEMA", ["Q"], "postgres", response)
        assert audit_id == 123
        
        # Test get_audit
        mock_conn.fetchrow.return_value = {
            "id": 123,
            "created_at": "2023-01-01",
            "schema_ddl": "SCHEMA",
            "queries": '["Q"]',
            "dialect": "postgres",
            "response_json": '{"summary": {"total_issues": 0, "high_severity": 0}, "issues": [], "rewrites": [], "indexes": []}',
            "user_id": "u1"
        }
        
        retrieved = await persistence.get_audit(123)
        assert retrieved["id"] == 123
        assert retrieved["user_id"] == "u1"



@pytest.mark.asyncio
async def test_get_persistence_factory():
    """Test the persistence factory function."""
    with patch("backend.core.config.settings.postgres_url", None):
        persistence = get_persistence()
        assert isinstance(persistence, SQLitePersistence)
        
    with patch("backend.core.config.settings.postgres_url", "postgresql://localhost/db"):
        if asyncpg is None:
            with pytest.raises(ImportError):
                get_persistence()
        else:
            persistence = get_persistence()
            assert isinstance(persistence, PostgresPersistence)


