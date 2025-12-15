"""Execute EXPLAIN queries against real databases."""

import logging
from typing import Literal, Optional

import sqlite3

logger = logging.getLogger(__name__)


class ExplainExecutor:
    """Execute EXPLAIN queries against databases."""

    def __init__(self, dialect: Literal["postgres", "sqlite"], connection_string: Optional[str] = None):
        self.dialect = dialect
        self.connection_string = connection_string
        self._connection = None

    async def execute_explain(self, query: str) -> Optional[str]:
        """
        Execute EXPLAIN query and return plan.

        Args:
            query: SQL query to explain

        Returns:
            EXPLAIN plan output or None if not available
        """
        if not self.connection_string:
            return None

        try:
            if self.dialect == "sqlite":
                return await self._explain_sqlite(query)
            elif self.dialect == "postgres":
                return await self._explain_postgres(query)
        except Exception as e:
            logger.error(f"Error executing EXPLAIN: {e}")
            return None

    async def _explain_sqlite(self, query: str) -> Optional[str]:
        """Execute EXPLAIN QUERY PLAN for SQLite."""
        try:
            import asyncio
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(
                None, sqlite3.connect, self.connection_string
            )
            cursor = conn.cursor()
            explain_query = f"EXPLAIN QUERY PLAN {query}"
            await loop.run_in_executor(None, cursor.execute, explain_query)
            # Wrap fetchall in a lambda to actually call the method
            results = await loop.run_in_executor(None, lambda: cursor.fetchall())
            await loop.run_in_executor(None, conn.close)

            # Format results
            plan_lines = []
            for row in results:
                plan_lines.append(" | ".join(str(cell) for cell in row))

            return "\n".join(plan_lines) if plan_lines else None
        except Exception as e:
            logger.error(f"SQLite EXPLAIN error: {e}")
            return None

    async def _explain_postgres(self, query: str) -> Optional[str]:
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
                    explain_query = f"EXPLAIN ANALYZE {query}"
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

