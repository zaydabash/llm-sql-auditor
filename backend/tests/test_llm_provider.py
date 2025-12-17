"""Tests for LLM providers."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.services.llm.provider import OpenAIProvider, get_provider
from backend.core.config import settings


@pytest.mark.asyncio
async def test_openai_provider_generate_explanation():
    """Test OpenAIProvider explanation generation."""
    with patch("backend.services.llm.provider.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        
        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test explanation"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OpenAIProvider(api_key="test-key")
        # Manually set the client to the mock to be sure
        provider.client = mock_client
        
        explanation = await provider.generate_explanation(
            schema_ddl="CREATE TABLE t1 (id INT);",
            query="SELECT * FROM t1;",
            issues=[],
            dialect="sqlite"
        )
        
        assert explanation == "Test explanation"

        mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_openai_provider_budget_exceeded():
    """Test OpenAIProvider when budget is exceeded."""
    with patch("backend.services.llm.provider.get_provider") as mock_get_provider:
        # We need to mock the cost_tracker inside the provider
        mock_tracker = MagicMock()
        mock_tracker.check_budget.return_value = {
            "within_budget": False,
            "total_cost": 150.0,
            "budget_limit": 100.0,
            "warning": False
        }
        
        provider = OpenAIProvider(api_key="test-key")
        provider.cost_tracker = mock_tracker
        
        explanation = await provider.generate_explanation(
            schema_ddl="CREATE TABLE t1 (id INT);",
            query="SELECT * FROM t1;",
            issues=[],
            dialect="sqlite"
        )
        
        assert "budget exceeded" in explanation.lower()



@pytest.mark.asyncio
async def test_openai_provider_error_handling():
    """Test OpenAIProvider error handling."""
    with patch("backend.services.llm.provider.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("rate_limit reached")

        
        provider = OpenAIProvider(api_key="test-key")
        provider.client = mock_client
        
        explanation = await provider.generate_explanation(
            schema_ddl="CREATE TABLE t1 (id INT);",
            query="SELECT * FROM t1;",
            issues=[],
            dialect="sqlite"
        )
        
        assert "Rate limit exceeded" in explanation



@pytest.mark.asyncio
async def test_openai_provider_propose_rewrite():
    """Test OpenAIProvider rewrite proposal."""
    with patch("backend.services.llm.provider.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        
        # Mock response with SQL block
        content = "Here is the optimized query:\n```sql\nSELECT id FROM users WHERE id = 1\n```\nRationale: Use index."
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OpenAIProvider(api_key="test-key")
        provider.client = mock_client
        
        rewrite = await provider.propose_rewrite(
            schema_ddl="CREATE TABLE users (id INT);",
            query="SELECT * FROM users",
            issues=[],
            dialect="sqlite"
        )
        
        assert rewrite is not None
        assert "SELECT id FROM users" in rewrite.optimized
        assert "Use index" in rewrite.rationale


def test_extract_optimized_sql():
    """Test extraction of SQL from LLM response."""
    from backend.services.llm.provider import _extract_optimized_sql
    
    content = "Some text\n```sql\nSELECT 1\n```\nMore text"
    assert _extract_optimized_sql(content) == "SELECT 1"
    
    content_no_block = "SELECT 1"
    assert _extract_optimized_sql(content_no_block) == ""



def test_extract_explanation():
    """Test extraction of explanation from LLM response."""
    from backend.services.llm.provider import _extract_explanation
    
    content = "```sql\nSELECT 1\n```\nThis is the explanation."
    assert "This is the explanation" in _extract_explanation(content)


def test_get_provider():
    """Test getting the configured provider."""
    with patch.object(settings, "openai_api_key", "test-key"):
        provider = get_provider()
        assert isinstance(provider, OpenAIProvider)
