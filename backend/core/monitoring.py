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


class MetricsCollector:
    """Collect application metrics."""

    def __init__(self):
        self.metrics = {
            "queries_audited": 0,
            "errors_occurred": 0,
            "llm_calls": 0,
            "average_audit_time": 0.0,
        }
        self._audit_times = []

    def record_audit(self, duration: float):
        """Record an audit operation."""
        self.metrics["queries_audited"] += 1
        self._audit_times.append(duration)
        if len(self._audit_times) > 100:
            self._audit_times.pop(0)
        self.metrics["average_audit_time"] = sum(self._audit_times) / len(self._audit_times)

    def record_error(self):
        """Record an error."""
        self.metrics["errors_occurred"] += 1

    def record_llm_call(self):
        """Record an LLM API call."""
        self.metrics["llm_calls"] += 1

    def get_metrics(self) -> dict:
        """Get current metrics."""
        return self.metrics.copy()


# Global metrics collector
metrics = MetricsCollector()
