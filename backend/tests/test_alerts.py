"""Tests for alerting logic."""

import pytest
from unittest.mock import MagicMock, patch
from backend.core.alerts import AlertManager


def test_alert_manager_init():
    """Test AlertManager initialization."""
    manager = AlertManager()
    assert len(manager.get_active_alerts()) == 0


def test_trigger_alert():
    """Test triggering an alert."""
    manager = AlertManager()
    manager._trigger_alert("TestAlert", "This is a test")
    
    alerts = manager.get_active_alerts()
    assert len(alerts) == 1
    assert alerts[0]["type"] == "TestAlert"
    assert alerts[0]["message"] == "This is a test"


def test_duplicate_alert():
    """Test that duplicate alerts are not added."""
    manager = AlertManager()
    manager._trigger_alert("TestAlert", "This is a test")
    manager._trigger_alert("TestAlert", "This is a test")
    
    assert len(manager.get_active_alerts()) == 1


@patch("backend.core.alerts.metrics")
def test_check_thresholds_high_error_rate(mock_metrics):
    """Test alerting on high error rate."""
    mock_metrics.get_metrics.return_value = {
        "queries_audited": 20,
        "errors_occurred": 5,  # 25% error rate
        "average_audit_time": 1.0
    }
    
    manager = AlertManager()
    manager.check_thresholds()
    
    alerts = manager.get_active_alerts()
    assert any(a["type"] == "HighErrorRate" for a in alerts)


@patch("backend.core.alerts.metrics")
def test_check_thresholds_high_latency(mock_metrics):
    """Test alerting on high latency."""
    mock_metrics.get_metrics.return_value = {
        "queries_audited": 20,
        "errors_occurred": 0,
        "average_audit_time": 10.0  # 10s latency
    }
    
    manager = AlertManager()
    manager.check_thresholds()
    
    alerts = manager.get_active_alerts()
    assert any(a["type"] == "HighLatency" for a in alerts)


@patch("backend.core.alerts.metrics")
def test_check_thresholds_no_traffic(mock_metrics):
    """Test that no alerts are triggered with low traffic."""
    mock_metrics.get_metrics.return_value = {
        "queries_audited": 5,
        "errors_occurred": 2,  # 40% error rate but low traffic
        "average_audit_time": 1.0
    }
    
    manager = AlertManager()
    manager.check_thresholds()
    
    assert len(manager.get_active_alerts()) == 0
