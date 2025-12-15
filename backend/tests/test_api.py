"""Tests for FastAPI endpoints."""

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "metrics" in data
    assert "version" in data


def test_audit_endpoint_basic():
    """Test audit endpoint with basic query."""
    request_data = {
        "schema": "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);",
        "queries": ["SELECT * FROM users;"],
        "dialect": "sqlite",
    }

    response = client.post("/api/audit", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert "summary" in data
    assert "issues" in data
    assert "rewrites" in data
    assert "indexes" in data
    assert "llmExplain" in data


def test_audit_endpoint_multiple_queries():
    """Test audit endpoint with multiple queries."""
    request_data = {
        "schema": "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);",
        "queries": [
            "SELECT * FROM users;",
            "SELECT * FROM users WHERE LOWER(email) = 'test';",
        ],
        "dialect": "postgres",
    }

    response = client.post("/api/audit", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert len(data["issues"]) > 0


def test_audit_endpoint_validation_error():
    """Test audit endpoint with invalid request."""
    request_data = {
        "schema": "",
        "queries": [],
        "dialect": "sqlite",
    }

    response = client.post("/api/audit", json=request_data)
    assert response.status_code == 422  # Validation error


def test_explain_endpoint():
    """Test explain endpoint."""
    request_data = {
        "schema": "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);",
        "query": "SELECT * FROM users;",
        "dialect": "sqlite",
    }

    response = client.post("/api/explain", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert "issues" in data
    assert "llmExplain" in data
