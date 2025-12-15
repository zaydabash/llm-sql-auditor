"""Authentication and authorization utilities."""

import hashlib
import hmac
import logging
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from backend.core.config import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> bool:
    """
    Verify API key from request header.

    Args:
        api_key: API key from header

    Returns:
        True if valid, raises HTTPException if invalid

    Raises:
        HTTPException: If authentication is required but key is missing/invalid
    """
    if not settings.require_auth:
        # Authentication not required
        return True

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header.",
        )

    if not settings.api_key:
        logger.warning("API key authentication required but no key configured")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: API key authentication not properly configured",
        )

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    return True


def generate_api_key() -> str:
    """
    Generate a new API key (for admin use).

    Returns:
        Random API key string
    """
    import secrets

    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage (one-way).

    Args:
        api_key: Plain API key

    Returns:
        Hashed API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()

