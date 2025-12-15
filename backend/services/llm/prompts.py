"""LLM prompts for SQL explanation and optimization."""

from typing import Literal

from backend.core.models import Issue


def get_system_prompt(dialect: Literal["postgres", "sqlite"]) -> str:
    """Get system prompt for LLM."""
    return f"""You are a rigorous SQL optimization assistant for {dialect.upper()}.

Your role is to:
1. Analyze SQL queries for performance issues
2. Suggest optimizations while preserving semantics
3. Explain issues clearly and concisely

CRITICAL RULES:
- NEVER change filtering logic or joins unless clearly incorrect
- Preserve query semantics exactly
- Prefer indexing and projection over wholesale rewrites
- Do NOT suggest destructive operations (DROP, DELETE, TRUNCATE)
- Do NOT expose or suggest revealing sensitive data
- Keep explanations under 200 words
- Provide bullet-point changelogs (3-6 items)

Return format:
1. Brief explanation of issues (≤200 words)
2. Optimized SQL (minimal changes)
3. Bullet-point changelog (3-6 items)
4. Optional footnotes on tradeoffs"""


def get_explanation_prompt(
    schema_ddl: str,
    query: str,
    issues: list[Issue],
    dialect: Literal["postgres", "sqlite"],
) -> str:
    """Generate user prompt for explanation."""
    issues_text = "\n".join(
        [f"- [{issue.code}] {issue.severity.upper()}: {issue.message}" for issue in issues]
    )

    return f"""Schema DDL:
{schema_ddl}

Original Query:
{query}

Detected Issues:
{issues_text if issues_text else "No issues detected"}

Please provide:
1. A concise explanation (≤200 words) of the performance issues and their impact
2. An optimized version of the SQL query (preserve semantics)
3. A bullet-point changelog (3-6 items) describing what changed and why

Format your response as:
EXPLANATION:
[your explanation]

OPTIMIZED_SQL:
[optimized query]

CHANGELOG:
- [change 1]
- [change 2]
..."""


def get_rewrite_prompt(
    schema_ddl: str,
    query: str,
    issues: list[Issue],
    dialect: Literal["postgres", "sqlite"],
) -> str:
    """Generate user prompt for query rewrite."""
    return get_explanation_prompt(schema_ddl, query, issues, dialect)
