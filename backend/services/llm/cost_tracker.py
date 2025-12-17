"""LLM cost tracking and budget management."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Pricing per 1K tokens (as of Dec 2024)
PRICING = {
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}


class CostTracker:
    """Track LLM usage and costs."""

    def __init__(self, db_path: str = "backend/db/llm_costs.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize cost tracking database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                input_cost REAL NOT NULL,
                output_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                operation TEXT,
                user_id TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON llm_usage(timestamp);
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_usage_user ON llm_usage(user_id);
        """
        )

        conn.commit()
        conn.close()

    def track_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation: str = "unknown",
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Track LLM usage and calculate cost.

        Returns:
            Dictionary with cost breakdown
        """
        pricing = PRICING.get(model, PRICING["gpt-4-turbo-preview"])

        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        total_cost = input_cost + output_cost

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO llm_usage 
                (model, input_tokens, output_tokens, input_cost, output_cost, total_cost, operation, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model,
                    input_tokens,
                    output_tokens,
                    input_cost,
                    output_cost,
                    total_cost,
                    operation,
                    user_id,
                ),
            )

            conn.commit()
            conn.close()

            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "input_cost": round(input_cost, 4),
                "output_cost": round(output_cost, 4),
                "total_cost": round(total_cost, 4),
            }
        except Exception as e:
            logger.error(f"Error tracking LLM usage: {e}")
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "input_cost": round(input_cost, 4),
                "output_cost": round(output_cost, 4),
                "total_cost": round(total_cost, 4),
            }

    def get_total_cost(
        self, user_id: Optional[str] = None, days: int = 30
    ) -> float:
        """Get total cost for the last N days."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if user_id:
                cursor.execute(
                    """
                    SELECT SUM(total_cost) FROM llm_usage
                    WHERE user_id = ? AND timestamp >= datetime('now', '-' || ? || ' days')
                    """,
                    (user_id, days),
                )
            else:
                cursor.execute(
                    """
                    SELECT SUM(total_cost) FROM llm_usage
                    WHERE timestamp >= datetime('now', '-' || ? || ' days')
                    """,
                    (days,),
                )

            result = cursor.fetchone()
            conn.close()

            return round(result[0] if result[0] else 0.0, 2)
        except Exception as e:
            logger.error(f"Error getting total cost: {e}")
            return 0.0

    def get_usage_report(self, days: int = 30) -> dict:
        """Get usage report for the last N days."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(total_cost) as total_cost,
                    AVG(total_cost) as avg_cost_per_request,
                    model
                FROM llm_usage
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
                GROUP BY model
                """,
                (days,),
            )

            rows = cursor.fetchall()
            conn.close()

            report = {
                "period_days": days,
                "by_model": [],
                "total_cost": 0.0,
                "total_requests": 0,
            }

            for row in rows:
                model_data = {
                    "model": row[5],
                    "requests": row[0],
                    "input_tokens": row[1],
                    "output_tokens": row[2],
                    "total_cost": round(row[3], 2),
                    "avg_cost": round(row[4], 4),
                }
                report["by_model"].append(model_data)
                report["total_cost"] += model_data["total_cost"]
                report["total_requests"] += model_data["requests"]

            report["total_cost"] = round(report["total_cost"], 2)

            return report
        except Exception as e:
            logger.error(f"Error generating usage report: {e}")
            return {
                "period_days": days,
                "by_model": [],
                "total_cost": 0.0,
                "total_requests": 0,
                "error": str(e),
            }

    def check_budget(
        self, budget_limit: float, user_id: Optional[str] = None, days: int = 30
    ) -> dict:
        """
        Check if usage is within budget.

        Returns:
            Dictionary with budget status
        """
        total_cost = self.get_total_cost(user_id=user_id, days=days)
        remaining = budget_limit - total_cost
        percentage_used = (total_cost / budget_limit * 100) if budget_limit > 0 else 0

        return {
            "budget_limit": budget_limit,
            "total_cost": total_cost,
            "remaining": round(remaining, 2),
            "percentage_used": round(percentage_used, 1),
            "within_budget": remaining > 0,
            "warning": percentage_used > 80,
        }


# Global cost tracker instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get global cost tracker instance."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker
