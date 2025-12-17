"""Integration tests for real EXPLAIN validation."""

import os
import sqlite3
import tempfile

import pytest
from backend.core.models import IndexSuggestion
from backend.services.performance_validator import validate_index_suggestion


@pytest.fixture
def temp_db():
    """Create a temporary database with some data for testing performance."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create a table and insert enough data to make a difference
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, name TEXT)")
    
    # Insert 1000 rows
    users = [(i, f"user{i}@example.com", f"User {i}") for i in range(1000)]
    cursor.executemany("INSERT INTO users VALUES (?, ?, ?)", users)
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_validate_index_suggestion_real_sqlite(temp_db):
    """Test real index validation on SQLite."""
    query = "SELECT * FROM users WHERE email = 'user500@example.com'"
    index = IndexSuggestion(
        table="users",
        columns=["email"],
        type="btree",
        rationale="Index on email for faster lookups",
    )
    
    result = await validate_index_suggestion(
        query=query,
        index_suggestion=index,
        dialect="sqlite",
        connection_string=temp_db,
    )
    
    assert result["validated"] is True
    assert "plan_before" in result
    assert "plan_after" in result
    assert "timing_before_ms" in result
    assert "timing_after_ms" in result
    assert "speedup" in result
    assert result["index_ddl"] == "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);"
    
    # Verify index was dropped afterwards
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_users_email'")
    assert cursor.fetchone() is None
    conn.close()


@pytest.mark.asyncio
async def test_validate_index_suggestion_failure_sqlite(temp_db):
    """Test validation failure when table doesn't exist."""
    query = "SELECT * FROM non_existent WHERE id = 1"
    index = IndexSuggestion(
        table="non_existent",
        columns=["id"],
        type="btree",
        rationale="Test",
    )
    
    result = await validate_index_suggestion(
        query=query,
        index_suggestion=index,
        dialect="sqlite",
        connection_string=temp_db,
    )
    
    assert result["validated"] is False
    assert "reason" in result
    assert "no such table" in result["reason"].lower()
