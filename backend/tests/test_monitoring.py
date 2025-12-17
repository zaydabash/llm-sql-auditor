"""Tests for monitoring and observability."""

import pytest
from backend.core.monitoring import MetricsCollector, PROMETHEUS_AVAILABLE


def test_metrics_collector_init():
    """Test MetricsCollector initialization."""
    collector = MetricsCollector()
    metrics = collector.get_metrics()
    assert metrics["queries_audited"] == 0
    assert metrics["errors_occurred"] == 0
    assert metrics["llm_calls"] == 0
    assert metrics["total_llm_cost"] == 0.0


def test_record_audit():
    """Test recording an audit operation."""
    collector = MetricsCollector()
    collector.record_audit(1.5, dialect="postgres")
    
    metrics = collector.get_metrics()
    assert metrics["queries_audited"] == 1
    assert metrics["average_audit_time"] == 1.5


def test_record_error():
    """Test recording an error."""
    collector = MetricsCollector()
    collector.record_error(error_type="validation")
    
    metrics = collector.get_metrics()
    assert metrics["errors_occurred"] == 1


def test_record_llm_call():
    """Test recording an LLM call."""
    collector = MetricsCollector()
    collector.record_llm_call(model="gpt-4", operation="explain", duration=2.0, cost=0.03)
    
    metrics = collector.get_metrics()
    assert metrics["llm_calls"] == 1
    assert metrics["total_llm_cost"] == 0.03


def test_get_prometheus_data():
    """Test getting Prometheus data."""
    collector = MetricsCollector()
    data = collector.get_prometheus_data()
    
    if PROMETHEUS_AVAILABLE:
        assert isinstance(data, str)
        # Should contain some metrics
        assert "# HELP" in data
    else:
        assert data == ""


def test_update_budget_usage():
    """Test updating budget usage metric."""
    collector = MetricsCollector()
    # This just calls the gauge, doesn't return anything, but shouldn't crash
    collector.update_budget_usage(85.0)


def test_track_execution_time(caplog):
    """Test track_execution_time context manager."""
    from backend.core.monitoring import track_execution_time
    import time
    
    with caplog.at_level("INFO"):
        with track_execution_time("test_op"):
            time.sleep(0.01)
            
    assert "test_op took" in caplog.text


def test_monitor_function_sync(caplog):
    """Test monitor_function decorator (sync)."""
    from backend.core.monitoring import monitor_function
    
    @monitor_function("sync_op")
    def sync_func():
        return "done"
        
    with caplog.at_level("INFO"):
        result = sync_func()
        
    assert result == "done"
    assert "sync_op took" in caplog.text


@pytest.mark.asyncio
async def test_monitor_function_async(caplog):
    """Test monitor_function decorator (async)."""
    from backend.core.monitoring import monitor_function
    import asyncio
    
    @monitor_function("async_op")
    async def async_func():
        await asyncio.sleep(0.01)
        return "done"
        
    with caplog.at_level("INFO"):
        result = await async_func()
        
    assert result == "done"
    assert "async_op took" in caplog.text


def test_metrics_collector_pop_logic():
    """Test MetricsCollector pop logic when more than 100 audits recorded."""
    collector = MetricsCollector()
    for i in range(110):
        collector.record_audit(float(i))
        
    metrics = collector.get_metrics()
    assert metrics["queries_audited"] == 110
    # Average should be of the last 100: (10 + ... + 109) / 100
    expected_avg = sum(range(10, 110)) / 100
    assert metrics["average_audit_time"] == expected_avg

