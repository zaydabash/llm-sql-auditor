"""Monitoring and observability utilities."""

import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)


@contextmanager
def track_execution_time(operation_name: str):
    """Context manager to track execution time."""
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        logger.info(f"{operation_name} took {elapsed:.3f}s")


def monitor_function(operation_name: str = None):
    """Decorator to monitor function execution."""

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            with track_execution_time(name):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            with track_execution_time(name):
                return func(*args, **kwargs)

        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        return sync_wrapper

    return decorator


try:
    from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Prometheus metrics
if PROMETHEUS_AVAILABLE:
    QUERIES_TOTAL = Counter("sqlauditor_queries_total", "Total queries audited", ["dialect"])
    ERRORS_TOTAL = Counter("sqlauditor_errors_total", "Total errors occurred", ["type"])
    LLM_CALLS_TOTAL = Counter("sqlauditor_llm_calls_total", "Total LLM API calls", ["model", "operation"])
    LLM_COST_TOTAL = Counter("sqlauditor_llm_cost_total", "Total LLM cost in USD")
    AUDIT_LATENCY = Histogram("sqlauditor_audit_latency_seconds", "Audit execution time in seconds")
    LLM_LATENCY = Histogram("sqlauditor_llm_latency_seconds", "LLM API latency in seconds")
    BUDGET_USAGE = Gauge("sqlauditor_llm_budget_usage_percent", "LLM budget usage percentage")


class MetricsCollector:
    """Collect application metrics."""

    def __init__(self):
        self.metrics = {
            "queries_audited": 0,
            "errors_occurred": 0,
            "llm_calls": 0,
            "total_llm_cost": 0.0,
            "average_audit_time": 0.0,
        }
        self._audit_times = []

    def record_audit(self, duration: float, dialect: str = "unknown"):
        """Record an audit operation."""
        self.metrics["queries_audited"] += 1
        self._audit_times.append(duration)
        if len(self._audit_times) > 100:
            self._audit_times.pop(0)
        self.metrics["average_audit_time"] = sum(self._audit_times) / len(self._audit_times)
        
        if PROMETHEUS_AVAILABLE:
            QUERIES_TOTAL.labels(dialect=dialect).inc()
            AUDIT_LATENCY.observe(duration)

    def record_error(self, error_type: str = "generic"):
        """Record an error."""
        self.metrics["errors_occurred"] += 1
        if PROMETHEUS_AVAILABLE:
            ERRORS_TOTAL.labels(type=error_type).inc()

    def record_llm_call(self, model: str, operation: str, duration: float, cost: float = 0.0):
        """Record an LLM API call."""
        self.metrics["llm_calls"] += 1
        self.metrics["total_llm_cost"] += cost
        
        if PROMETHEUS_AVAILABLE:
            LLM_CALLS_TOTAL.labels(model=model, operation=operation).inc()
            LLM_LATENCY.observe(duration)
            if cost > 0:
                LLM_COST_TOTAL.inc(cost)

    def update_budget_usage(self, percentage: float):
        """Update budget usage metric."""
        if PROMETHEUS_AVAILABLE:
            BUDGET_USAGE.set(percentage)

    def get_metrics(self) -> dict:
        """Get current metrics."""
        return self.metrics.copy()

    def get_prometheus_data(self) -> str:
        """Get metrics in Prometheus format."""
        if PROMETHEUS_AVAILABLE:
            return generate_latest().decode("utf-8")
        return ""


# Global metrics collector
metrics = MetricsCollector()

