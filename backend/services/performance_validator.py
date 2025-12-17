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

    executor = ExplainExecutor(dialect, connection_string)
    index_ddl = _generate_index_ddl(index_suggestion, dialect)
    index_name = f"idx_{index_suggestion.table}_{'_'.join(index_suggestion.columns)}"

    try:
        # 1. Get baseline performance
        plan_before = await executor.execute_explain(query, analyze=True)
        timing_before = await executor.execute_query_with_timing(query)
        
        # 2. Create index
        created, error = await executor.run_ddl(index_ddl)
        if not created:
            return {
                "validated": False,
                "reason": f"Failed to create index: {error}",
            }

        # 3. Get performance with index
        plan_after = await executor.execute_explain(query, analyze=True)
        timing_after = await executor.execute_query_with_timing(query)

        # 4. Clean up (DROP INDEX)
        drop_ddl = f"DROP INDEX {index_name};"
        if dialect == "postgres":
            drop_ddl = f"DROP INDEX IF EXISTS {index_name};"
        await executor.run_ddl(drop_ddl)


        # 5. Analyze results
        analysis = _analyze_explain_plans(plan_before, plan_after, dialect)
        
        # Calculate improvement metrics
        time_before = timing_before.get("time_ms", 0)
        time_after = timing_after.get("time_ms", 0)
        speedup = (time_before / time_after) if time_after > 0 else 0

        return {
            "validated": True,
            "plan_before": plan_before,
            "plan_after": plan_after,
            "timing_before_ms": round(time_before, 2),
            "timing_after_ms": round(time_after, 2),
            "speedup": round(speedup, 2),
            "analysis": analysis,
            "index_ddl": index_ddl,
        }
    except Exception as e:
        logger.error(f"Error validating index suggestion: {e}")
        # Attempt cleanup just in case
        try:
            drop_ddl = f"DROP INDEX IF EXISTS {index_name};" if dialect == "postgres" else f"DROP INDEX {index_name};"
            await executor.run_ddl(drop_ddl)
        except:
            pass
            
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
