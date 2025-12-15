"""Tests for security features."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.security import validate_sql_input, validate_schema_input, sanitize_error_message

client = TestClient(app)


def test_validate_sql_input_valid():
    """Test SQL input validation with valid input."""
    validate_sql_input("SELECT * FROM users;")
    validate_sql_input("SELECT id, email FROM users WHERE id = 1;")


def test_validate_sql_input_empty():
    """Test SQL input validation rejects empty input."""
    with pytest.raises(Exception):
        validate_sql_input("")
    with pytest.raises(Exception):
        validate_sql_input("   ")


def test_validate_sql_input_too_large():
    """Test SQL input validation rejects oversized input."""
    large_query = "SELECT * FROM users; " * 10000
    with pytest.raises(Exception):
        validate_sql_input(large_query, max_length=1000)


def test_validate_sql_input_dangerous_patterns():
    """Test SQL input validation detects dangerous patterns."""
    dangerous_queries = [
        "SELECT * FROM users; DROP TABLE users;",
        "SELECT * FROM users UNION SELECT * FROM passwords;",
    ]

    for query in dangerous_queries:
        with pytest.raises(Exception):
            validate_sql_input(query)


def test_validate_schema_input():
    """Test schema input validation."""
    validate_schema_input("CREATE TABLE users (id INTEGER);")
    
    with pytest.raises(Exception):
        validate_schema_input("")
    
    large_schema = "CREATE TABLE users (id INTEGER); " * 10000
    with pytest.raises(Exception):
        validate_schema_input(large_schema, max_length=1000)


def test_sanitize_error_message():
    """Test error message sanitization."""
    # Should sanitize stack traces
    error = Exception("Traceback:\nFile '/path/to/file.py', line 10\n  raise ValueError('test')")
    sanitized = sanitize_error_message(error)
    assert "Traceback" not in sanitized or "internal error" in sanitized.lower()

    # Should limit length
    long_error = Exception("A" * 500)
    sanitized = sanitize_error_message(long_error)
    assert len(sanitized) <= 203  # 200 + "..."

