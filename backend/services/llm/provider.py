"""LLM provider interface and OpenAI implementation."""

import logging
from typing import Literal, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config import settings
from backend.core.models import Issue, Rewrite
from backend.services.llm.prompts import get_explanation_prompt, get_rewrite_prompt

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


class LLMProvider:
    """Abstract LLM provider interface."""

    async def generate_explanation(
        self,
        schema_ddl: str,
        query: str,
        issues: list[Issue],
        dialect: Literal["postgres", "sqlite"],
    ) -> str:
        """Generate natural language explanation of issues."""
        raise NotImplementedError

    async def propose_rewrite(
        self,
        schema_ddl: str,
        query: str,
        issues: list[Issue],
        dialect: Literal["postgres", "sqlite"],
    ) -> Optional[Rewrite]:
        """Propose optimized SQL rewrite."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI API provider implementation."""

    def __init__(self, api_key: str):
        if AsyncOpenAI is None:
            raise ImportError("openai package not installed")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4-turbo-preview"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_explanation(
        self,
        schema_ddl: str,
        query: str,
        issues: list[Issue],
        dialect: Literal["postgres", "sqlite"],
    ) -> str:
        """Generate explanation using OpenAI API."""
        from backend.services.llm.prompts import get_system_prompt

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": get_system_prompt(dialect)},
                    {
                        "role": "user",
                        "content": get_explanation_prompt(schema_ddl, query, issues, dialect),
                    },
                ],
                temperature=0.3,
                max_tokens=500,
                timeout=settings.llm_timeout,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return f"Error generating explanation: {str(e)}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def propose_rewrite(
        self,
        schema_ddl: str,
        query: str,
        issues: list[Issue],
        dialect: Literal["postgres", "sqlite"],
    ) -> Optional[Rewrite]:
        """Propose rewrite using OpenAI API."""
        from backend.services.llm.prompts import get_system_prompt

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": get_system_prompt(dialect)},
                    {
                        "role": "user",
                        "content": get_rewrite_prompt(schema_ddl, query, issues, dialect),
                    },
                ],
                temperature=0.3,
                max_tokens=1000,
                timeout=settings.llm_timeout,
            )
            content = response.choices[0].message.content or ""

            # Parse response to extract optimized SQL
            optimized_sql = _extract_optimized_sql(content)
            rationale = _extract_explanation(content)

            if optimized_sql:
                return Rewrite(
                    original=query,
                    optimized=optimized_sql,
                    rationale=rationale,
                )
            return None
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None


class StubProvider(LLMProvider):
    """Stub provider that returns placeholder responses when no API key is configured."""

    async def generate_explanation(
        self,
        schema_ddl: str,
        query: str,
        issues: list[Issue],
        dialect: Literal["postgres", "sqlite"],
    ) -> str:
        """Return stub explanation."""
        if not issues:
            return "No issues detected. Query appears well-optimized."

        issue_summary = ", ".join([f"{issue.code}" for issue in issues[:3]])
        return f"""This query has {len(issues)} potential optimization opportunities: {issue_summary}.

To get detailed LLM-generated explanations, please configure OPENAI_API_KEY in your environment.

The detected issues include:
{chr(10).join([f"- {issue.code}: {issue.message}" for issue in issues[:5]])}"""

    async def propose_rewrite(
        self,
        schema_ddl: str,
        query: str,
        issues: list[Issue],
        dialect: Literal["postgres", "sqlite"],
    ) -> Optional[Rewrite]:
        """Return stub rewrite."""
        if not issues:
            return None

        # Simple stub rewrite - just return original with a note
        return Rewrite(
            original=query,
            optimized=query,  # No actual rewrite without LLM
            rationale="Configure OPENAI_API_KEY to get optimized SQL suggestions.",
        )


def get_provider() -> LLMProvider:
    """Get configured LLM provider."""
    api_key = settings.openai_api_key
    if api_key and AsyncOpenAI:
        try:
            return OpenAIProvider(api_key)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI provider: {e}, using stub")
            return StubProvider()
    return StubProvider()


def _extract_optimized_sql(content: str) -> str:
    """Extract optimized SQL from LLM response."""
    # Look for OPTIMIZED_SQL: or ```sql blocks
    if "OPTIMIZED_SQL:" in content:
        parts = content.split("OPTIMIZED_SQL:")
        if len(parts) > 1:
            sql_part = parts[1].split("CHANGELOG:")[0].strip()
            # Remove markdown code blocks if present
            sql_part = sql_part.replace("```sql", "").replace("```", "").strip()
            return sql_part

    # Try to find SQL in code blocks
    if "```sql" in content:
        parts = content.split("```sql")
        if len(parts) > 1:
            sql_part = parts[1].split("```")[0].strip()
            return sql_part

    # Fallback: return empty
    return ""


def _extract_explanation(content: str) -> str:
    """Extract explanation/rationale from LLM response."""
    if "EXPLANATION:" in content:
        parts = content.split("EXPLANATION:")
        if len(parts) > 1:
            explanation = parts[1].split("OPTIMIZED_SQL:")[0].strip()
            return explanation

    # Fallback: return first paragraph
    lines = content.split("\n")
    explanation_lines = []
    for line in lines:
        if line.strip() and not line.strip().startswith("```"):
            explanation_lines.append(line.strip())
            if len(explanation_lines) >= 3:
                break

    return " ".join(explanation_lines) if explanation_lines else "No explanation provided."
