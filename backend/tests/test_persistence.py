"""Tests for the persistence layer."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    import asyncpg
except ImportError:
    asyncpg = None

import backend.services.persistence as persistence_module
from backend.core.models import AuditResponse, Summary
from backend.services.persistence import PostgresPersistence, SQLitePersistence, get_persistence


class _FakeAcquire:
    """Async context manager mimicking asyncpg pool.acquire()."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        return False


def _fake_asyncpg(conn):
    """Build a fake asyncpg module whose create_pool yields a pool wrapping conn."""
    pool = MagicMock()
    pool.acquire = lambda: _FakeAcquire(conn)
    return SimpleNamespace(create_pool=AsyncMock(return_value=pool))


@pytest.fixture
def db_path(tmp_path):
    """Fixture for temporary database path."""
    return str(tmp_path / "test_audit_history.sqlite")


@pytest.mark.asyncio
async def test_sqlite_persistence_init(db_path):
    """Test SQLite database initialization."""
    SQLitePersistence(db_path)
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
        assert retrieved is not None
        assert retrieved["id"] == 123
        assert retrieved["user_id"] == "u1"



@pytest.mark.asyncio
async def test_postgres_persistence_with_fake_asyncpg():
    """Exercise PostgresPersistence end-to-end with a fully faked asyncpg module."""
    conn = AsyncMock()
    conn.fetchrow.return_value = {"id": 7}
    fake = _fake_asyncpg(conn)

    with patch.object(persistence_module, "asyncpg", fake):
        persistence = PostgresPersistence("postgresql://user:pass@localhost/db")

        # init_db issues CREATE TABLE / CREATE INDEX
        await persistence.init_db()
        assert conn.execute.await_count == 2

        response = AuditResponse(
            summary=Summary(total_issues=0, high_severity=0),
            issues=[],
            rewrites=[],
            indexes=[],
        )

        # save_audit returns the new row id
        audit_id = await persistence.save_audit("SCHEMA", ["Q"], "postgres", response)
        assert audit_id == 7

        # get_audit maps the row into a dict (JSONB already decoded)
        conn.fetchrow.return_value = {
            "id": 7,
            "created_at": "2023-01-01",
            "schema_ddl": "SCHEMA",
            "queries": ["Q"],
            "dialect": "postgres",
            "response_json": {"summary": {}, "issues": []},
            "user_id": "u1",
        }
        retrieved = await persistence.get_audit(7)
        assert retrieved is not None
        assert retrieved["id"] == 7
        assert retrieved["queries"] == ["Q"]

        # get_audit returns None when the row is missing
        conn.fetchrow.return_value = None
        assert await persistence.get_audit(999) is None

        # list_recent_audits maps rows into summaries
        conn.fetch.return_value = [
            {"id": 7, "created_at": "2023-01-01", "dialect": "postgres", "user_id": "u1"}
        ]
        recent = await persistence.list_recent_audits(limit=5)
        assert recent[0]["id"] == 7


@pytest.mark.asyncio
async def test_postgres_persistence_error_paths():
    """get_audit and list_recent_audits swallow errors and return safe defaults."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = Exception("boom")
    conn.fetch.side_effect = Exception("boom")
    fake = _fake_asyncpg(conn)

    with patch.object(persistence_module, "asyncpg", fake):
        persistence = PostgresPersistence("postgresql://user:pass@localhost/db")
        assert await persistence.get_audit(1) is None
        assert await persistence.list_recent_audits() == []

        # save_audit re-raises on failure
        response = AuditResponse(
            summary=Summary(total_issues=0, high_severity=0),
            issues=[],
            rewrites=[],
            indexes=[],
        )
        with pytest.raises(Exception):
            await persistence.save_audit("SCHEMA", ["Q"], "postgres", response)


def test_postgres_persistence_requires_asyncpg():
    """PostgresPersistence raises ImportError when asyncpg is unavailable."""
    with patch.object(persistence_module, "asyncpg", None):
        with pytest.raises(ImportError):
            PostgresPersistence("postgresql://localhost/db")


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


