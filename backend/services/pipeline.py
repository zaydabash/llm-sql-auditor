"""Main analysis pipeline orchestrating all components."""

import logging
from typing import Literal

from backend.core.models import AuditResponse, Issue, Rewrite, Summary
from backend.core.dialects import extract_table_info, parse_schema
from backend.services.analyzer.cost_estimator import estimate_cost
from backend.services.analyzer.index_advisor import recommend_indexes
from backend.services.analyzer.parser import parse_query
from backend.services.analyzer.rules_engine import run_all_rules
from backend.services.llm.provider import get_provider

logger = logging.getLogger(__name__)


async def audit_queries(
    schema_ddl: str,
    queries: list[str],
    dialect: Literal["postgres", "sqlite"],
    use_llm: bool = True,
) -> AuditResponse:
    """
    Run full audit pipeline on queries.

    Args:
        schema_ddl: Database schema DDL
        queries: List of SQL queries to audit
        dialect: SQL dialect
        use_llm: Whether to use LLM for explanations (requires API key)

    Returns:
        AuditResponse with issues, rewrites, indexes, and explanations
    """
    all_issues: list[Issue] = []
    all_rewrites: list[Rewrite] = []
    all_indexes: list = []

    # Parse schema
    try:
        schema_ast = parse_schema(schema_ddl, dialect)
        table_info = extract_table_info(schema_ast, schema_ddl)
    except Exception as e:
        logger.error(f"Failed to parse schema: {e}")
        table_info = {"tables": {}, "row_hints": {}}
    
    # Ensure table_info has the expected structure
    if not isinstance(table_info, dict):
        table_info = {"tables": {}, "row_hints": {}}

    # Process each query
    for idx, query in enumerate(queries):
        try:
            query_ast = parse_query(query, dialect)

            # Run rules engine
            issues = run_all_rules(query_ast, idx, table_info)
            all_issues.extend(issues)

            # Estimate cost
            cost_score, improvement_text = estimate_cost(query_ast, table_info, dialect)

            # Recommend indexes
            indexes = recommend_indexes(query_ast, table_info, dialect)
            all_indexes.extend(indexes)

            # Generate LLM rewrite if enabled
            if use_llm:
                llm_provider = get_provider()
                rewrite = await llm_provider.propose_rewrite(
                    schema_ddl, query, issues, dialect
                )
                if rewrite:
                    rewrite.query_index = idx
                    all_rewrites.append(rewrite)

        except Exception as e:
            logger.error(f"Error processing query {idx}: {e}")
            all_issues.append(
                Issue(
                    code="PARSE_ERROR",
                    severity="error",
                    message=f"Failed to parse query: {str(e)}",
                    snippet=query[:200],
                    query_index=idx,
                )
            )

    # Generate overall LLM explanation if enabled
    llm_explain = ""
    if use_llm and queries:
        try:
            llm_provider = get_provider()
            # Use first query for overall explanation
            llm_explain = await llm_provider.generate_explanation(
                schema_ddl, queries[0], all_issues[:10], dialect
            )
        except Exception as e:
            logger.error(f"Error generating LLM explanation: {e}")
            llm_explain = "Error generating explanation."

    # Calculate summary
    high_severity = sum(1 for issue in all_issues if issue.severity == "error")
    total_issues = len(all_issues)

    # Get improvement estimate from cost estimator (use average)
    if queries:
        try:
            first_query_ast = parse_query(queries[0], dialect)
            _, improvement_text = estimate_cost(first_query_ast, table_info, dialect)
        except Exception:
            improvement_text = None
    else:
        improvement_text = None

    summary = Summary(
        total_issues=total_issues,
        high_severity=high_severity,
        est_improvement=improvement_text,
    )

    return AuditResponse(
        summary=summary,
        issues=all_issues,
        rewrites=all_rewrites,
        indexes=all_indexes,
        llm_explain=llm_explain,
    )

