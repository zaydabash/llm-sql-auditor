"""LLM provider interface and OpenAI implementation."""

import logging
import time
from typing import Literal, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config import settings
from backend.core.models import Issue, Rewrite
from backend.core.monitoring import metrics
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

    def __init__(self, api_key: str, model: Optional[str] = None):
        if AsyncOpenAI is None:
            raise ImportError("openai package not installed")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model or settings.llm_model
        
        # Initialize cost tracking
        if settings.llm_enable_cost_tracking:
            from backend.services.llm.cost_tracker import get_cost_tracker
            self.cost_tracker = get_cost_tracker()
        else:
            self.cost_tracker = None

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

        # Check budget before making call
        if self.cost_tracker:
            budget_status = self.cost_tracker.check_budget(settings.llm_budget_monthly)
            if not budget_status["within_budget"]:
                return f"LLM budget exceeded (${budget_status['total_cost']:.2f} / ${budget_status['budget_limit']:.2f}). Please increase budget or wait for next billing cycle."
            if budget_status["warning"]:
                logger.warning(f"LLM budget at {budget_status['percentage_used']}% (${budget_status['total_cost']:.2f} / ${budget_status['budget_limit']:.2f})")

        try:
            start_time = time.time()
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": get_system_prompt(dialect)},
                    {
                        "role": "user",
                        "content": get_explanation_prompt(schema_ddl, query, issues, dialect),
                    },
                ],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout,
            )
            
            # Track cost and metrics
            if response.usage:
                duration = time.time() - start_time
                cost = 0.0
                if self.cost_tracker:
                    cost_info = self.cost_tracker.track_usage(
                        model=self.model,
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        operation="explain",
                    )
                    cost = cost_info.get("total_cost", 0.0)
                logger.info(f"LLM cost: ${cost:.4f} (input: {response.usage.prompt_tokens} tokens, output: {response.usage.completion_tokens} tokens)")
            
                metrics.record_llm_call(
                    model=self.model,
                    operation="explain",
                    duration=duration,
                    cost=cost
                )
            
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            metrics.record_error()
            error_msg = str(e).lower()
            if "rate_limit" in error_msg or "429" in error_msg:
                return "Rate limit exceeded. Please wait a moment and try again."
            elif "invalid_api_key" in error_msg or "401" in error_msg:
                return "Invalid API key. Please check your OPENAI_API_KEY configuration."
            elif "insufficient_quota" in error_msg:
                return "OpenAI account quota exceeded. Please check your OpenAI billing."
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

        # Check budget before making call
        if self.cost_tracker:
            budget_status = self.cost_tracker.check_budget(settings.llm_budget_monthly)
            if not budget_status["within_budget"]:
                logger.warning(f"LLM budget exceeded, skipping rewrite suggestion")
                return None

        try:
            start_time = time.time()
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": get_system_prompt(dialect)},
                    {
                        "role": "user",
                        "content": get_rewrite_prompt(schema_ddl, query, issues, dialect),
                    },
                ],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout,
            )
            
            # Track cost and metrics
            if response.usage:
                duration = time.time() - start_time
                cost = 0.0
                if self.cost_tracker:
                    cost_info = self.cost_tracker.track_usage(
                        model=self.model,
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        operation="rewrite",
                    )
                    cost = cost_info.get("total_cost", 0.0)
                logger.info(f"LLM cost: ${cost:.4f}")
            
                metrics.record_llm_call(
                    model=self.model,
                    operation="rewrite",
                    duration=duration,
                    cost=cost
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
            metrics.record_error()
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
