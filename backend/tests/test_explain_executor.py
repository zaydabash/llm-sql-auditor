"""Tests for the ExplainExecutor."""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock, AsyncMock
from backend.db.explain_executor import ExplainExecutor

@pytest.mark.asyncio
async def test_explain_sqlite_success():
    """Test successful SQLite EXPLAIN."""
    executor = ExplainExecutor(dialect="sqlite", connection_string=":memory:")
    
    with patch("sqlite3.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [(0, "SCAN TABLE t1")]
        
        plan = await executor.execute_explain("SELECT * FROM t1")
        
        assert plan == "0 | SCAN TABLE t1"
        mock_cursor.execute.assert_called_with("EXPLAIN QUERY PLAN SELECT * FROM t1")

@pytest.mark.asyncio
async def test_explain_sqlite_failure():
    """Test SQLite EXPLAIN failure."""
    executor = ExplainExecutor(dialect="sqlite", connection_string=":memory:")
    
    with patch("sqlite3.connect") as mock_connect:
        mock_connect.side_effect = Exception("Connection error")
        
        plan = await executor.execute_explain("SELECT * FROM t1")
        assert plan is None

@pytest.mark.asyncio
async def test_run_ddl_sqlite():
    """Test running DDL on SQLite."""
    executor = ExplainExecutor(dialect="sqlite", connection_string=":memory:")
    
    with patch("sqlite3.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        success, error = await executor.run_ddl("CREATE INDEX idx_t1_id ON t1(id)")
        
        assert success is True
        assert error is None
        mock_cursor.execute.assert_called_with("CREATE INDEX idx_t1_id ON t1(id)")
        mock_conn.commit.assert_called_once()

@pytest.mark.asyncio
async def test_execute_query_with_timing_sqlite():
    """Test timed query execution on SQLite."""
    executor = ExplainExecutor(dialect="sqlite", connection_string=":memory:")
    
    with patch("sqlite3.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        result = await executor.execute_query_with_timing("SELECT * FROM t1")
        
        assert "time_ms" in result
        assert "error" not in result
        mock_cursor.execute.assert_called_with("SELECT * FROM t1")
        mock_cursor.fetchall.assert_called_once()

@pytest.mark.asyncio
async def test_explain_postgres_success():
    """Test successful PostgreSQL EXPLAIN."""
    executor = ExplainExecutor(dialect="postgres", connection_string="postgresql://user:pass@host/db")
    
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [{"QUERY PLAN": "Seq Scan on t1"}]
        
        plan = await executor.execute_explain("SELECT * FROM t1")
        
        assert plan == "Seq Scan on t1"
        mock_cursor.execute.assert_called_with("EXPLAIN SELECT * FROM t1")

@pytest.mark.asyncio
async def test_run_ddl_postgres():
    """Test running DDL on PostgreSQL."""
    executor = ExplainExecutor(dialect="postgres", connection_string="postgresql://user:pass@host/db")
    
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        success, error = await executor.run_ddl("CREATE INDEX idx_t1_id ON t1(id)")
        
        assert success is True
        assert error is None
        mock_cursor.execute.assert_called_with("CREATE INDEX idx_t1_id ON t1(id)")
        mock_conn.commit.assert_called_once()

def test_explain_executor_no_conn_string():
    """Test executor behavior without connection string."""
    executor = ExplainExecutor(dialect="sqlite")
    
    # These should return None or error dict/tuple
    import asyncio
    loop = asyncio.get_event_loop()
    
    plan = loop.run_until_complete(executor.execute_explain("SELECT 1"))
    assert plan is None
    
    success, error = loop.run_until_complete(executor.run_ddl("CREATE TABLE x(id INT)"))
    assert success is False
    assert error == "No connection string"
    
    result = loop.run_until_complete(executor.execute_query_with_timing("SELECT 1"))
    assert result["error"] == "No connection string"

@pytest.mark.asyncio
async def test_execute_query_with_timing_postgres():
    """Test timed query execution on PostgreSQL."""
    executor = ExplainExecutor(dialect="postgres", connection_string="postgresql://user:pass@host/db")
    
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        result = await executor.execute_query_with_timing("SELECT * FROM t1")
        
        assert "time_ms" in result
        assert "error" not in result
        mock_cursor.execute.assert_called_with("SELECT * FROM t1")
        mock_cursor.fetchall.assert_called_once()

@pytest.mark.asyncio
async def test_explain_postgres_analyze():
    """Test PostgreSQL EXPLAIN ANALYZE."""
    executor = ExplainExecutor(dialect="postgres", connection_string="postgresql://user:pass@host/db")
    
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [{"QUERY PLAN": "Seq Scan on t1 (actual time=0.01..0.02 rows=10 loops=1)"}]
        
        plan = await executor.execute_explain("SELECT * FROM t1", analyze=True)
        
        assert "actual time" in plan
        mock_cursor.execute.assert_called_with("EXPLAIN ANALYZE SELECT * FROM t1")

@pytest.mark.asyncio
async def test_explain_postgres_failure():
    """Test PostgreSQL EXPLAIN failure."""
    executor = ExplainExecutor(dialect="postgres", connection_string="postgresql://user:pass@host/db")
    
    with patch("psycopg2.connect") as mock_connect:
        mock_connect.side_effect = Exception("Postgres error")
        
        plan = await executor.execute_explain("SELECT * FROM t1")
        assert plan is None

def test_explain_executor_close():

    """Test close method."""
    executor = ExplainExecutor(dialect="sqlite")
    mock_conn = MagicMock()
    executor._connection = mock_conn
    
    executor.close()
    mock_conn.close.assert_called_once()
    assert executor._connection is None
