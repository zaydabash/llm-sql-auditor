"""Tests for LLM cost tracking."""

import os
import tempfile

import pytest
from backend.services.llm.cost_tracker import CostTracker, PRICING


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    yield db_path
    
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def tracker(temp_db):
    """Create CostTracker instance."""
    return CostTracker(db_path=temp_db)


def test_cost_tracker_init(temp_db):
    """Test CostTracker initialization."""
    tracker = CostTracker(db_path=temp_db)
    assert os.path.exists(temp_db)


def test_track_usage_gpt4_turbo(tracker):
    """Test tracking GPT-4 Turbo usage."""
    result = tracker.track_usage(
        model="gpt-4-turbo-preview",
        input_tokens=1000,
        output_tokens=500,
        operation="explain",
    )
    
    assert result["input_tokens"] == 1000
    assert result["output_tokens"] == 500
    assert result["input_cost"] == 0.01  # 1000/1000 * 0.01
    assert result["output_cost"] == 0.015  # 500/1000 * 0.03
    assert result["total_cost"] == 0.025


def test_track_usage_gpt35(tracker):
    """Test tracking GPT-3.5 usage."""
    result = tracker.track_usage(
        model="gpt-3.5-turbo",
        input_tokens=2000,
        output_tokens=1000,
        operation="rewrite",
    )
    
    assert result["input_cost"] == 0.001  # 2000/1000 * 0.0005
    assert result["output_cost"] == 0.0015  # 1000/1000 * 0.0015
    assert result["total_cost"] == 0.0025


def test_get_total_cost(tracker):
    """Test getting total cost."""
    # Track multiple usages
    tracker.track_usage("gpt-4-turbo-preview", 1000, 500, "explain")
    tracker.track_usage("gpt-4-turbo-preview", 2000, 1000, "rewrite")
    
    total = tracker.get_total_cost(days=30)
    
    # First: 0.01 + 0.015 = 0.025
    # Second: 0.02 + 0.03 = 0.05
    # Total: 0.075
    assert total == 0.08  # Rounded


def test_get_total_cost_by_user(tracker):
    """Test getting total cost by user."""
    tracker.track_usage("gpt-4-turbo-preview", 1000, 500, "explain", user_id="user1")
    tracker.track_usage("gpt-4-turbo-preview", 1000, 500, "explain", user_id="user2")
    
    user1_cost = tracker.get_total_cost(user_id="user1", days=30)
    user2_cost = tracker.get_total_cost(user_id="user2", days=30)
    
    assert user1_cost == 0.03  # Rounded
    assert user2_cost == 0.03


def test_get_usage_report(tracker):
    """Test getting usage report."""
    tracker.track_usage("gpt-4-turbo-preview", 1000, 500, "explain")
    tracker.track_usage("gpt-3.5-turbo", 2000, 1000, "rewrite")
    
    report = tracker.get_usage_report(days=30)
    
    assert report["period_days"] == 30
    assert report["total_requests"] == 2
    assert len(report["by_model"]) == 2
    
    # Check model breakdown
    models = {m["model"]: m for m in report["by_model"]}
    assert "gpt-4-turbo-preview" in models
    assert "gpt-3.5-turbo" in models
    
    gpt4 = models["gpt-4-turbo-preview"]
    assert gpt4["requests"] == 1
    assert gpt4["input_tokens"] == 1000
    assert gpt4["output_tokens"] == 500


def test_check_budget_within_limit(tracker):
    """Test budget check when within limit."""
    tracker.track_usage("gpt-4-turbo-preview", 1000, 500, "explain")
    
    status = tracker.check_budget(budget_limit=10.0, days=30)
    
    assert status["within_budget"] is True
    assert status["warning"] is False
    assert status["budget_limit"] == 10.0
    assert status["total_cost"] == 0.03  # Rounded
    assert status["remaining"] > 0


def test_check_budget_exceeded(tracker):
    """Test budget check when exceeded."""
    # Track enough usage to exceed $1 budget
    for _ in range(50):
        tracker.track_usage("gpt-4-turbo-preview", 1000, 500, "explain")
    
    status = tracker.check_budget(budget_limit=1.0, days=30)
    
    assert status["within_budget"] is False
    assert status["remaining"] < 0


def test_check_budget_warning(tracker):
    """Test budget warning at 80%."""
    # Track usage to get to ~85% of $1 budget
    for _ in range(34):
        tracker.track_usage("gpt-4-turbo-preview", 1000, 500, "explain")
    
    status = tracker.check_budget(budget_limit=1.0, days=30)
    
    assert status["warning"] is True
    assert status["percentage_used"] > 80


def test_track_usage_unknown_model(tracker):
    """Test tracking usage for unknown model (should use default pricing)."""
    result = tracker.track_usage(
        model="unknown-model",
        input_tokens=1000,
        output_tokens=500,
        operation="test",
    )
    
    # Should use gpt-4-turbo-preview pricing as default
    assert result["total_cost"] == 0.025


def test_get_usage_report_empty(tracker):
    """Test usage report when no data."""
    report = tracker.get_usage_report(days=30)
    
    assert report["total_requests"] == 0
    assert report["total_cost"] == 0.0
    assert len(report["by_model"]) == 0
