"""Centralized error handling and logging."""

import logging
from typing import Optional

from fastapi import HTTPException

from backend.core.security import sanitize_error_message

logger = logging.getLogger(__name__)


class AuditError(Exception):
    """Base exception for audit-related errors."""

    pass


class ParseError(AuditError):
    """SQL parsing error."""

    pass


class ValidationError(AuditError):
    """Input validation error."""

    pass


def handle_audit_error(error: Exception, context: Optional[str] = None) -> HTTPException:
    """
    Handle audit errors and return appropriate HTTP response.

    Args:
        error: The exception that occurred
        context: Additional context about where the error occurred

    Returns:
        HTTPException with sanitized error message
    """
    if isinstance(error, HTTPException):
        return error

    # Log full error with context
    error_context = f" in {context}" if context else ""
    logger.error(f"Audit error{error_context}: {error}", exc_info=True)

    # Determine status code based on error type
    if isinstance(error, ValidationError):
        status_code = 400
    elif isinstance(error, ParseError):
        status_code = 422
    else:
        status_code = 500

    # Sanitize error message
    sanitized_msg = sanitize_error_message(error)

    return HTTPException(status_code=status_code, detail=sanitized_msg)


def log_audit_event(event_type: str, details: dict, user_id: Optional[str] = None):
    """
    Log audit events for monitoring and debugging.

    Args:
        event_type: Type of event (e.g., 'query_audited', 'error_occurred')
        details: Event details
        user_id: Optional user identifier
    """
    log_data = {
        "event_type": event_type,
        "details": details,
    }
    if user_id:
        log_data["user_id"] = user_id

    logger.info(f"Audit event: {log_data}")
