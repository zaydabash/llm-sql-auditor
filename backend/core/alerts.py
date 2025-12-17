"""Alerting logic for SQL Auditor."""

import logging
from typing import Optional

from backend.core.monitoring import metrics

logger = logging.getLogger(__name__)

# Alerting thresholds
THRESHOLDS = {
    "error_rate_percent": 5.0,
    "avg_latency_seconds": 5.0,
    "llm_cost_daily_usd": 10.0,
}


class AlertManager:
    """Manage application alerts."""

    def __init__(self):
        self.active_alerts = []

    def check_thresholds(self):
        """Check current metrics against thresholds."""
        current_metrics = metrics.get_metrics()
        
        # 1. Check error rate
        total_queries = current_metrics["queries_audited"]
        if total_queries > 10:  # Only alert after some traffic
            error_rate = (current_metrics["errors_occurred"] / total_queries) * 100
            if error_rate > THRESHOLDS["error_rate_percent"]:
                self._trigger_alert(
                    "HighErrorRate",
                    f"Error rate is {error_rate:.1f}% (threshold: {THRESHOLDS['error_rate_percent']}%)"
                )

        # 2. Check latency
        avg_time = current_metrics["average_audit_time"]
        if avg_time > THRESHOLDS["avg_latency_seconds"]:
            self._trigger_alert(
                "HighLatency",
                f"Average audit time is {avg_time:.1f}s (threshold: {THRESHOLDS['avg_latency_seconds']}s)"
            )

    def _trigger_alert(self, alert_type: str, message: str):
        """Trigger an alert (log for now, could send email/slack)."""
        alert = {"type": alert_type, "message": message}
        if alert not in self.active_alerts:
            self.active_alerts.append(alert)
            logger.error(f"ALERT: [{alert_type}] {message}")

    def get_active_alerts(self) -> list[dict]:
        """Get list of active alerts."""
        return self.active_alerts


# Global alert manager
alert_manager = AlertManager()
