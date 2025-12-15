"""Persistence layer for audit history."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.core.models import AuditResponse

logger = logging.getLogger(__name__)


class AuditHistory:
    """Store and retrieve audit history."""

    def __init__(self, db_path: str = "backend/db/audit_history.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize audit history database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                schema_ddl TEXT,
                queries TEXT,
                dialect TEXT,
                response_json TEXT,
                user_id TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_history(created_at);
        """)

        conn.commit()
        conn.close()

    def save_audit(
        self,
        schema_ddl: str,
        queries: list[str],
        dialect: str,
        response: AuditResponse,
        user_id: Optional[str] = None,
    ) -> int:
        """
        Save audit result to history.

        Returns:
            Audit record ID
        """
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
            logger.error(f"Error saving audit history: {e}")
            raise

    def get_audit(self, audit_id: int) -> Optional[dict]:
        """Retrieve audit by ID."""
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
            logger.error(f"Error retrieving audit history: {e}")
            return None

    def list_recent_audits(self, limit: int = 10) -> list[dict]:
        """List recent audits."""
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
            logger.error(f"Error listing audit history: {e}")
            return []

