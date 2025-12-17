"""Tests for LLM provider module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.core.models import Issue
from backend.services.llm.provider import (
    OpenAIProvider,
    StubProvider,
    get_provider,
)


@pytest.mark.asyncio
async def test_stub_provider_generate_explanation():
    """Test StubProvider explanation generation."""
    provider = StubProvider()

    issues = [
        Issue(code="R001", severity="warn", message="SELECT * usage", rule="SELECT_STAR"),
        Issue(code="R004", severity="warn", message="Non-SARGable", rule="NON_SARGABLE"),
    ]

    result = await provider.generate_explanation(
        schema_ddl="CREATE TABLE users (id INTEGER);",
        query="SELECT * FROM users;",
        issues=issues,
        dialect="postgres",
    )

    assert result is not None
    assert "R001" in result
    assert "OPENAI_API_KEY" in result


@pytest.mark.asyncio
async def test_stub_provider_propose_rewrite():
    """Test StubProvider rewrite proposal."""
    provider = StubProvider()

    issues = [
        Issue(code="R001", severity="warn", message="SELECT * usage", rule="SELECT_STAR"),
    ]

    result = await provider.propose_rewrite(
        schema_ddl="CREATE TABLE users (id INTEGER);",
        query="SELECT * FROM users;",
        issues=issues,
        dialect="postgres",
    )

    assert result is not None
    assert result.original == "SELECT * FROM users;"
    assert "OPENAI_API_KEY" in result.rationale


@pytest.mark.asyncio
async def test_stub_provider_no_issues():
    """Test StubProvider with no issues."""
    provider = StubProvider()

    result = await provider.generate_explanation(
        schema_ddl="CREATE TABLE users (id INTEGER);",
        query="SELECT id FROM users WHERE id = 1;",
        issues=[],
        dialect="postgres",
    )

    assert "No issues detected" in result


def test_get_provider_no_api_key():
    """Test get_provider returns StubProvider when no API key."""
    with patch("backend.services.llm.provider.settings") as mock_settings:
        mock_settings.openai_api_key = None

        provider = get_provider()
        assert isinstance(provider, StubProvider)


def test_get_provider_with_api_key():
    """Test get_provider returns OpenAIProvider with API key."""
    with patch("backend.services.llm.provider.settings") as mock_settings:
        with patch("backend.services.llm.provider.AsyncOpenAI"):
            mock_settings.openai_api_key = "test-key"

            provider = get_provider()
            assert isinstance(provider, OpenAIProvider)


@pytest.mark.asyncio
async def test_openai_provider_error_handling():
    """Test OpenAIProvider handles errors gracefully."""
    with patch("backend.services.llm.provider.AsyncOpenAI") as mock_openai:
        client = MagicMock()
        mock_openai.return_value = client
        client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

        provider = OpenAIProvider(api_key="test-key")

        issues = [Issue(code="R001", severity="warn", message="Test", rule="TEST")]

        result = await provider.generate_explanation(
            schema_ddl="CREATE TABLE test (id INTEGER);",
            query="SELECT * FROM test;",
            issues=issues,
            dialect="postgres",
        )

        # Should return error message, not crash
        assert "Error" in result


@pytest.mark.asyncio
async def test_openai_provider_success():
    """Test OpenAIProvider successful call."""
    with patch("backend.services.llm.provider.AsyncOpenAI") as mock_openai:
        client = MagicMock()
        mock_openai.return_value = client

        completion = MagicMock()
        completion.choices = [MagicMock()]
        completion.choices[0].message.content = "This query has performance issues."

        client.chat.completions.create = AsyncMock(return_value=completion)

        provider = OpenAIProvider(api_key="test-key")

        issues = [Issue(code="R001", severity="warn", message="SELECT *", rule="SELECT_STAR")]

        result = await provider.generate_explanation(
            schema_ddl="CREATE TABLE users (id INTEGER);",
            query="SELECT * FROM users;",
            issues=issues,
            dialect="postgres",
        )

        assert result == "This query has performance issues."
        client.chat.completions.create.assert_called_once()
