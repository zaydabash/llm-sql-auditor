"""Tests for the FastAPI application."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.models import AuditResponse, Summary

client = TestClient(app)

@pytest.fixture
def mock_verify_api_key():
    with patch("backend.app.verify_api_key") as mock:
        mock.return_value = True
        yield mock

def test_health_check():
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "metrics" in response.json()

def test_get_metrics():
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"

@pytest.mark.asyncio
async def test_audit_endpoint(mock_verify_api_key):
    """Test audit endpoint."""
    payload = {
        "schema_ddl": "CREATE TABLE t1 (id INT);",
        "queries": ["SELECT * FROM t1"],
        "dialect": "sqlite"
    }

    mock_response = AuditResponse(
        summary=Summary(total_issues=1, high_severity=0, est_improvement="Test"),
        issues=[],
        rewrites=[],
        indexes=[],
        llm_explain="Test explanation"
    )

    with patch("backend.app.audit_queries", new_callable=AsyncMock) as mock_audit:
        mock_audit.return_value = mock_response

        response = client.post("/api/audit", json=payload)

        assert response.status_code == 200
        assert response.json()["llmExplain"] == "Test explanation"
        mock_audit.assert_called_once()

@pytest.mark.asyncio
async def test_explain_endpoint(mock_verify_api_key):
    """Test explain endpoint."""
    payload = {
        "schema_ddl": "CREATE TABLE t1 (id INT);",
        "query": "SELECT * FROM t1",
        "dialect": "sqlite"
    }

    mock_response = AuditResponse(
        summary=Summary(total_issues=1, high_severity=0, est_improvement="Test"),
        issues=[],
        rewrites=[],
        indexes=[],
        llm_explain="Test explanation"
    )

    with patch("backend.app.audit_queries", new_callable=AsyncMock) as mock_audit:
        mock_audit.return_value = mock_response

        response = client.post("/api/explain", json=payload)

        assert response.status_code == 200
        assert response.json()["llmExplain"] == "Test explanation"
        mock_audit.assert_called_once()


def test_get_llm_costs(mock_verify_api_key):
    """Test LLM costs endpoint."""
    with patch("backend.services.llm.cost_tracker.get_cost_tracker") as mock_get_tracker:

        mock_tracker = MagicMock()
        mock_tracker.get_usage_report.return_value = {"total": 0}
        mock_tracker.check_budget.return_value = {"within_budget": True}
        mock_get_tracker.return_value = mock_tracker

        client.get("/api/llm/costs")

def test_get_llm_costs_error(mock_verify_api_key):
    """Test LLM costs endpoint error handling."""
    with patch("backend.services.llm.cost_tracker.get_cost_tracker") as mock_get_tracker:
        mock_get_tracker.side_effect = Exception("Tracker error")

        response = client.get("/api/llm/costs")
        assert response.status_code == 500
        assert "Failed to retrieve cost information" in response.json()["detail"]

@pytest.mark.asyncio
async def test_audit_endpoint_error(mock_verify_api_key):
    """Test audit endpoint error handling."""
    payload = {
        "schema_ddl": "CREATE TABLE t1 (id INT);",
        "queries": ["SELECT * FROM t1"],
        "dialect": "sqlite"
    }

    with patch("backend.app.audit_queries", new_callable=AsyncMock) as mock_audit:
        mock_audit.side_effect = Exception("Audit failed")

        response = client.post("/api/audit", json=payload)
        assert response.status_code == 500
        # Sanitize error message might change it, but should be a string
        assert isinstance(response.json()["detail"], str)


def test_get_audit_history(mock_verify_api_key):
    """Test listing audit history."""
    mock_persistence = MagicMock()
    mock_persistence.list_recent_audits = AsyncMock(
        return_value=[{"id": 1, "dialect": "sqlite", "user_id": None}]
    )

    with patch("backend.services.persistence.get_persistence", return_value=mock_persistence):
        response = client.get("/api/history?limit=5")

        assert response.status_code == 200
        assert response.json()[0]["id"] == 1
        mock_persistence.list_recent_audits.assert_awaited_once_with(limit=5)


def test_get_audit_history_error(mock_verify_api_key):
    """Test audit history listing error handling."""
    with patch("backend.services.persistence.get_persistence", side_effect=Exception("DB error")):
        response = client.get("/api/history")

        assert response.status_code == 500
        assert "Failed to retrieve audit history" in response.json()["detail"]


def test_get_audit_detail(mock_verify_api_key):
    """Test retrieving a single audit by ID."""
    mock_persistence = MagicMock()
    mock_persistence.get_audit = AsyncMock(return_value={"id": 42, "user_id": "u1"})

    with patch("backend.services.persistence.get_persistence", return_value=mock_persistence):
        response = client.get("/api/history/42")

        assert response.status_code == 200
        assert response.json()["id"] == 42
        mock_persistence.get_audit.assert_awaited_once_with(42)


def test_get_audit_detail_not_found(mock_verify_api_key):
    """Test retrieving a missing audit returns 404."""
    mock_persistence = MagicMock()
    mock_persistence.get_audit = AsyncMock(return_value=None)

    with patch("backend.services.persistence.get_persistence", return_value=mock_persistence):
        response = client.get("/api/history/999")

        assert response.status_code == 404
        assert "Audit not found" in response.json()["detail"]


def test_get_audit_detail_error(mock_verify_api_key):
    """Test audit detail error handling."""
    with patch("backend.services.persistence.get_persistence", side_effect=Exception("DB error")):
        response = client.get("/api/history/1")

        assert response.status_code == 500
        assert "Failed to retrieve audit detail" in response.json()["detail"]

