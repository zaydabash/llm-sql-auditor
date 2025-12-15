"""Security utilities: rate limiting, input validation, CORS."""

import re
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)


def get_cors_middleware(allowed_origins: Optional[list[str]] = None) -> CORSMiddleware:
    """Get CORS middleware with secure defaults."""
    if allowed_origins is None:
        # In production, this should be set from environment
        allowed_origins = ["http://localhost:5173", "http://localhost:3000"]

    return CORSMiddleware(
        app=None,  # Will be set by FastAPI
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=3600,
    )


def validate_sql_input(query: str, max_length: int = 100_000) -> None:
    """Validate SQL input to prevent injection and oversized queries."""
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if len(query) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Query exceeds maximum length of {max_length} characters",
        )

    # Basic SQL injection pattern detection (not comprehensive, but catches obvious attempts)
    dangerous_patterns = [
        r";\s*(DROP|DELETE|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)",
        r"UNION\s+.*SELECT",
        r"EXEC\s*\(",
        r"xp_cmdshell",
        r"LOAD_FILE\s*\(",
    ]

    query_upper = query.upper()
    for pattern in dangerous_patterns:
        if re.search(pattern, query_upper, re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail="Query contains potentially dangerous SQL patterns",
            )


def validate_schema_input(schema: str, max_length: int = 500_000) -> None:
    """Validate schema DDL input."""
    if not schema or not schema.strip():
        raise HTTPException(status_code=400, detail="Schema cannot be empty")

    if len(schema) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Schema exceeds maximum length of {max_length} characters",
        )


def sanitize_error_message(error: Exception) -> str:
    """Sanitize error messages to prevent information leakage."""
    error_str = str(error)

    # Remove potential sensitive information
    # Don't expose internal paths, stack traces, etc.
    if "Traceback" in error_str or "File" in error_str and ".py" in error_str:
        return "An internal error occurred. Please check your input and try again."

    # Limit error message length
    if len(error_str) > 200:
        return error_str[:200] + "..."

    return error_str

