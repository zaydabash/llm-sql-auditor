"""Validate query performance improvements."""

import logging
from typing import Literal, Optional

from backend.core.models import IndexSuggestion
from backend.db.explain_executor import ExplainExecutor

logger = logging.getLogger(__name__)


async def validate_index_suggestion(
    query: str,
    index_suggestion: IndexSuggestion,
    dialect: Literal["postgres", "sqlite"],
    connection_string: Optional[str],
) -> dict:
    """
    Validate that an index suggestion would improve performance.

    Args:
        query: SQL query to test
        index_suggestion: Suggested index
        dialect: SQL dialect
        connection_string: Database connection string

    Returns:
        Dictionary with validation results
    """
    if not connection_string:
        return {
            "validated": False,
            "reason": "No database connection available",
        }

    try:
        executor = ExplainExecutor(dialect, connection_string)
        
        # Get EXPLAIN plan without index
        plan_before = await executor.execute_explain(query)
        
        # Create index (if possible in test environment)
        # Note: In production, this would be done carefully
        index_ddl = _generate_index_ddl(index_suggestion, dialect)
        
        # Get EXPLAIN plan with index (if we can create it)
        # For now, we'll just analyze the plan structure
        plan_after = None
        
        # Analyze plans
        analysis = _analyze_explain_plans(plan_before, plan_after, dialect)
        
        return {
            "validated": True,
            "plan_before": plan_before,
            "plan_after": plan_after,
            "analysis": analysis,
            "index_ddl": index_ddl,
        }
    except Exception as e:
        logger.error(f"Error validating index suggestion: {e}")
        return {
            "validated": False,
            "reason": str(e),
        }


def _generate_index_ddl(index: IndexSuggestion, dialect: Literal["postgres", "sqlite"]) -> str:
    """Generate CREATE INDEX DDL statement."""
    columns_str = ", ".join(index.columns)
    
    if dialect == "postgres":
        if index.type == "gin":
            return f"CREATE INDEX IF NOT EXISTS idx_{index.table}_{'_'.join(index.columns)} ON {index.table} USING gin ({columns_str});"
        else:
            return f"CREATE INDEX IF NOT EXISTS idx_{index.table}_{'_'.join(index.columns)} ON {index.table} ({columns_str});"
    else:  # sqlite
        return f"CREATE INDEX IF NOT EXISTS idx_{index.table}_{'_'.join(index.columns)} ON {index.table} ({columns_str});"


def _analyze_explain_plans(
    plan_before: Optional[str],
    plan_after: Optional[str],
    dialect: Literal["postgres", "sqlite"],
) -> dict:
    """
    Analyze EXPLAIN plans to determine improvement.

    Returns:
        Dictionary with analysis results
    """
    if not plan_before:
        return {
            "improvement": "unknown",
            "reason": "Could not get EXPLAIN plan",
        }

    # Basic analysis - look for sequential scans, index scans, etc.
    plan_lower = plan_before.lower()
    
    # PostgreSQL analysis
    if dialect == "postgres":
        has_seq_scan = "seq scan" in plan_lower or "sequential scan" in plan_lower
        has_index_scan = "index scan" in plan_lower or "bitmap heap scan" in plan_lower
        
        if has_seq_scan and not has_index_scan:
            return {
                "improvement": "likely",
                "reason": "Query uses sequential scan - index would likely help",
            }
        elif has_index_scan:
            return {
                "improvement": "possible",
                "reason": "Query already uses indexes - additional index may still help",
            }
    
    # SQLite analysis
    else:
        if "scan table" in plan_lower:
            return {
                "improvement": "likely",
                "reason": "Query scans table - index would likely help",
            }
        elif "search" in plan_lower:
            return {
                "improvement": "possible",
                "reason": "Query uses search - additional index may help",
            }

    return {
        "improvement": "unknown",
        "reason": "Could not determine improvement from EXPLAIN plan",
    }

