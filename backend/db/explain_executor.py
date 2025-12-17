"""Execute EXPLAIN queries against real databases."""

import logging
import sqlite3
from typing import Literal, Optional

logger = logging.getLogger(__name__)


class ExplainExecutor:
    """Execute EXPLAIN queries against databases."""

    def __init__(
        self, dialect: Literal["postgres", "sqlite"], connection_string: Optional[str] = None
    ):
        self.dialect = dialect
        self.connection_string = connection_string
        self._connection = None

    async def execute_explain(self, query: str, analyze: bool = False) -> Optional[str]:
        """
        Execute EXPLAIN query and return plan.

        Args:
            query: SQL query to explain
            analyze: Whether to use EXPLAIN ANALYZE (PostgreSQL only)

        Returns:
            EXPLAIN plan output or None if not available
        """
        if not self.connection_string:
            return None

        try:
            if self.dialect == "sqlite":
                return await self._explain_sqlite(query)
            elif self.dialect == "postgres":
                return await self._explain_postgres(query, analyze)
        except Exception as e:
            logger.error(f"Error executing EXPLAIN: {e}")
            return None

    async def run_ddl(self, ddl: str) -> tuple[bool, Optional[str]]:
        """
        Execute DDL statement (e.g., CREATE INDEX).

        Returns:
            Tuple of (success, error_message)
        """
        if not self.connection_string:
            return False, "No connection string"

        try:
            import asyncio
            loop = asyncio.get_event_loop()

            if self.dialect == "sqlite":
                def _execute_ddl():
                    conn = sqlite3.connect(self.connection_string)
                    try:
                        cursor = conn.cursor()
                        cursor.execute(ddl)
                        conn.commit()
                        return True, None
                    except Exception as e:
                        return False, str(e)
                    finally:
                        conn.close()
            else:  # postgres
                import psycopg2
                def _execute_ddl():
                    conn = psycopg2.connect(self.connection_string)
                    try:
                        cursor = conn.cursor()
                        cursor.execute(ddl)
                        conn.commit()
                        return True, None
                    except Exception as e:
                        return False, str(e)
                    finally:
                        conn.close()

            return await loop.run_in_executor(None, _execute_ddl)
        except Exception as e:
            logger.error(f"Error executing DDL: {e}")
            return False, str(e)


    async def execute_query_with_timing(self, query: str) -> dict:
        """
        Execute query and measure execution time.

        Returns:
            Dictionary with execution time and results
        """
        if not self.connection_string:
            return {"time_ms": 0, "error": "No connection string"}

        import time
        import asyncio
        loop = asyncio.get_event_loop()

        try:
            if self.dialect == "sqlite":
                def _execute_timed():
                    conn = sqlite3.connect(self.connection_string)
                    try:
                        cursor = conn.cursor()
                        start_time = time.perf_counter()
                        cursor.execute(query)
                        cursor.fetchall()
                        end_time = time.perf_counter()
                        return {"time_ms": (end_time - start_time) * 1000}
                    finally:
                        conn.close()
            else:  # postgres
                import psycopg2
                def _execute_timed():
                    conn = psycopg2.connect(self.connection_string)
                    try:
                        cursor = conn.cursor()
                        start_time = time.perf_counter()
                        cursor.execute(query)
                        cursor.fetchall()
                        end_time = time.perf_counter()
                        return {"time_ms": (end_time - start_time) * 1000}
                    finally:
                        conn.close()

            return await loop.run_in_executor(None, _execute_timed)
        except Exception as e:
            logger.error(f"Error executing timed query: {e}")
            return {"time_ms": 0, "error": str(e)}

    async def _explain_sqlite(self, query: str) -> Optional[str]:
        """Execute EXPLAIN QUERY PLAN for SQLite."""
        try:
            import asyncio

            # Run all database operations in a single executor call to avoid thread safety issues
            def _execute_explain():
                """Execute EXPLAIN in a blocking function."""
                conn = sqlite3.connect(self.connection_string)
                try:
                    cursor = conn.cursor()
                    explain_query = f"EXPLAIN QUERY PLAN {query}"
                    cursor.execute(explain_query)
                    results = cursor.fetchall()
                    return results
                finally:
                    conn.close()

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, _execute_explain)

            # Format results
            plan_lines = []
            for row in results:
                plan_lines.append(" | ".join(str(cell) for cell in row))

            return "\n".join(plan_lines) if plan_lines else None
        except Exception as e:
            logger.error(f"SQLite EXPLAIN error: {e}")
            return None

    async def _explain_postgres(self, query: str, analyze: bool = False) -> Optional[str]:
        """Execute EXPLAIN ANALYZE for PostgreSQL."""
        try:
            import asyncio

            import psycopg2
            from psycopg2.extras import RealDictCursor

            # Run blocking I/O operations in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()

            def _execute_explain():
                """Execute EXPLAIN in a blocking function."""
                conn = psycopg2.connect(self.connection_string)
                try:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
                    explain_query = f"{prefix} {query}"
                    cursor.execute(explain_query)
                    results = cursor.fetchall()
                    return results
                finally:
                    conn.close()

            results = await loop.run_in_executor(None, _execute_explain)

            # Format results
            plan_lines = []
            for row in results:
                plan_lines.append(row.get("QUERY PLAN", str(row)))

            return "\n".join(plan_lines) if plan_lines else None
        except Exception as e:
            logger.error(f"PostgreSQL EXPLAIN error: {e}")
            return None

    def close(self):
        """Close database connection."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

