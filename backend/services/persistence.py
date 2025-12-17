import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union

try:
    import asyncpg
except ImportError:
    asyncpg = None

from backend.core.models import AuditResponse
from backend.core.config import settings


logger = logging.getLogger(__name__)


class PersistenceProvider(ABC):
    """Base class for audit history persistence."""

    @abstractmethod
    async def save_audit(
        self,
        schema_ddl: str,
        queries: list[str],
        dialect: str,
        response: AuditResponse,
        user_id: Optional[str] = None,
    ) -> Union[int, str]:
        """Save audit result."""
        pass

    @abstractmethod
    async def get_audit(self, audit_id: Union[int, str]) -> Optional[dict]:
        """Retrieve audit by ID."""
        pass

    @abstractmethod
    async def list_recent_audits(self, limit: int = 10) -> list[dict]:
        """List recent audits."""
        pass


class SQLitePersistence(PersistenceProvider):
    """SQLite implementation of audit history."""

    def __init__(self, db_path: str = "backend/db/audit_history.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize audit history database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                schema_ddl TEXT,
                queries TEXT,
                dialect TEXT,
                response_json TEXT,
                user_id TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_history(created_at);
        """
        )

        conn.commit()
        conn.close()

    async def save_audit(
        self,
        schema_ddl: str,
        queries: list[str],
        dialect: str,
        response: AuditResponse,
        user_id: Optional[str] = None,
    ) -> int:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            response_json = json.dumps(response.model_dump(), default=str)

            cursor.execute(
                """
                INSERT INTO audit_history (schema_ddl, queries, dialect, response_json, user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (schema_ddl, json.dumps(queries), dialect, response_json, user_id),
            )

            record_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return record_id
        except Exception as e:
            logger.error(f"Error saving audit history to SQLite: {e}")
            raise

    async def get_audit(self, audit_id: int) -> Optional[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM audit_history WHERE id = ?",
                (audit_id,),
            )

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return {
                "id": row[0],
                "created_at": row[1],
                "schema_ddl": row[2],
                "queries": json.loads(row[3]),
                "dialect": row[4],
                "response": json.loads(row[5]),
                "user_id": row[6],
            }
        except Exception as e:
            logger.error(f"Error retrieving audit history from SQLite: {e}")
            return None

    async def list_recent_audits(self, limit: int = 10) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, created_at, dialect, user_id
                FROM audit_history
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )

            rows = cursor.fetchall()
            conn.close()

            return [
                {
                    "id": row[0],
                    "created_at": row[1],
                    "dialect": row[2],
                    "user_id": row[3],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error listing audit history from SQLite: {e}")
            return []


class PostgresPersistence(PersistenceProvider):
    """PostgreSQL implementation of audit history using asyncpg."""

    def __init__(self, dsn: str):
        if asyncpg is None:
            raise ImportError(
                "asyncpg is required for PostgresPersistence. "
                "Install it with 'pip install asyncpg' or 'poetry add asyncpg'."
            )
        self.dsn = dsn
        self._pool = None


    async def _get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.dsn)
        return self._pool

    async def init_db(self):
        """Initialize PostgreSQL schema."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_history (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    schema_ddl TEXT,
                    queries JSONB,
                    dialect TEXT,
                    response_json JSONB,
                    user_id TEXT
                )
            """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_history(created_at)"
            )

    async def save_audit(
        self,
        schema_ddl: str,
        queries: list[str],
        dialect: str,
        response: AuditResponse,
        user_id: Optional[str] = None,
    ) -> int:
        try:
            pool = await self._get_pool()
            response_json = json.dumps(response.model_dump(), default=str)
            
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO audit_history (schema_ddl, queries, dialect, response_json, user_id)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    schema_ddl, json.dumps(queries), dialect, response_json, user_id
                )
                return row['id']
        except Exception as e:
            logger.error(f"Error saving audit history to Postgres: {e}")
            raise

    async def get_audit(self, audit_id: int) -> Optional[dict]:
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM audit_history WHERE id = $1",
                    audit_id
                )
                if not row:
                    return None
                
                return {
                    "id": row['id'],
                    "created_at": row['created_at'],
                    "schema_ddl": row['schema_ddl'],
                    "queries": json.loads(row['queries']) if isinstance(row['queries'], str) else row['queries'],
                    "dialect": row['dialect'],
                    "response": json.loads(row['response_json']) if isinstance(row['response_json'], str) else row['response_json'],
                    "user_id": row['user_id'],
                }
        except Exception as e:
            logger.error(f"Error retrieving audit history from Postgres: {e}")
            return None

    async def list_recent_audits(self, limit: int = 10) -> list[dict]:
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, created_at, dialect, user_id
                    FROM audit_history
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit
                )
                return [
                    {
                        "id": row['id'],
                        "created_at": row['created_at'],
                        "dialect": row['dialect'],
                        "user_id": row['user_id'],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Error listing audit history from Postgres: {e}")
            return []


def get_persistence() -> PersistenceProvider:
    """Factory function to get the configured persistence provider."""
    if settings.postgres_url:
        return PostgresPersistence(settings.postgres_url)
    return SQLitePersistence()


# For backward compatibility
AuditHistory = SQLitePersistence

