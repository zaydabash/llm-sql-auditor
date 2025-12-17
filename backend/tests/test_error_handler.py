"""Tests for the error handler."""

import pytest
from fastapi import HTTPException
from backend.core.error_handler import handle_audit_error, ValidationError, ParseError, log_audit_event


def test_handle_audit_error_http_exception():
    """Test handling of existing HTTPException."""
    exc = HTTPException(status_code=403, detail="Forbidden")
    result = handle_audit_error(exc)
    assert result == exc


def test_handle_audit_error_validation_error():
    """Test handling of ValidationError."""
    exc = ValidationError("Invalid input")
    result = handle_audit_error(exc)
    assert result.status_code == 400
    assert result.detail == "Invalid input"


def test_handle_audit_error_parse_error():
    """Test handling of ParseError."""
    exc = ParseError("Syntax error")
    result = handle_audit_error(exc)
    assert result.status_code == 422
    assert result.detail == "Syntax error"


def test_handle_audit_error_generic_exception():
    """Test handling of generic Exception."""
    exc = Exception("Something went wrong")
    result = handle_audit_error(exc)
    assert result.status_code == 500
    assert result.detail == "Something went wrong"


def test_log_audit_event(caplog):
    """Test logging of audit events."""
    import logging
    with caplog.at_level(logging.INFO):
        log_audit_event("test_event", {"key": "value"}, user_id="user123")
        assert "Audit event" in caplog.text
        assert "test_event" in caplog.text
        assert "user123" in caplog.text
