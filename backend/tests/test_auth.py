"""Tests for authentication."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.auth import generate_api_key, hash_api_key, verify_api_key
from backend.core.config import settings

client = TestClient(app)


def test_generate_api_key():
    """Test API key generation."""
    key1 = generate_api_key()
    key2 = generate_api_key()
    
    assert len(key1) > 20
    assert key1 != key2


def test_hash_api_key():
    """Test API key hashing."""
    key = "test-key"
    hashed = hash_api_key(key)
    
    assert len(hashed) == 64  # SHA256 hex length
    assert hashed != key
    assert hash_api_key(key) == hashed  # Deterministic


def test_verify_api_key_no_auth_required():
    """Test API key verification when auth not required."""
    original_require = settings.require_auth
    settings.require_auth = False
    
    try:
        # Should pass without key
        result = verify_api_key(None)
        assert result is True
    finally:
        settings.require_auth = original_require


def test_verify_api_key_missing():
    """Test API key verification with missing key when required."""
    original_require = settings.require_auth
    original_key = settings.api_key
    
    settings.require_auth = True
    settings.api_key = "test-key"
    
    try:
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None)
        assert exc_info.value.status_code == 401
    finally:
        settings.require_auth = original_require
        settings.api_key = original_key


def test_verify_api_key_invalid():
    """Test API key verification with invalid key."""
    original_require = settings.require_auth
    original_key = settings.api_key
    
    settings.require_auth = True
    settings.api_key = "correct-key"
    
    try:
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key("wrong-key")
        assert exc_info.value.status_code == 401
    finally:
        settings.require_auth = original_require
        settings.api_key = original_key


def test_verify_api_key_valid():
    """Test API key verification with valid key."""
    original_require = settings.require_auth
    original_key = settings.api_key
    
    settings.require_auth = True
    settings.api_key = "test-key"
    
    try:
        result = verify_api_key("test-key")
        assert result is True
    finally:
        settings.require_auth = original_require
        settings.api_key = original_key

