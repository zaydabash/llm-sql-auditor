"""Main analysis pipeline orchestrating all components."""

import logging
import time
from typing import Literal

from backend.core.config import settings
from backend.core.dialects import extract_table_info, parse_schema
from backend.core.models import AuditResponse, Issue, Rewrite, Summary
from backend.core.monitoring import metrics, track_execution_time
from backend.db.explain_executor import ExplainExecutor
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
    validate_performance: bool = False,
) -> AuditResponse:
    """Run full audit pipeline on queries with monitoring."""
    start_time = time.time()

    try:
        with track_execution_time("audit_queries"):
            return await _audit_queries_internal(
                schema_ddl, queries, dialect, use_llm, validate_performance
            )
    finally:
        duration = time.time() - start_time
        metrics.record_audit(duration)


async def _audit_queries_internal(
    schema_ddl: str,
    queries: list[str],
    dialect: Literal["postgres", "sqlite"],
    use_llm: bool = True,
    validate_performance: bool = False,
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

            # Execute EXPLAIN if enabled and connection available
            explain_plan = None
            if settings.enable_explain:
                try:
                    connection_string = (
                        settings.postgres_connection_string
                        if dialect == "postgres"
                        else settings.sqlite_connection_string or settings.demo_db_path
                    )
                    if connection_string:
                        explain_executor = ExplainExecutor(dialect, connection_string)
                        explain_plan = await explain_executor.execute_explain(query)
                        if explain_plan:
                            logger.info(f"EXPLAIN plan for query {idx}:\n{explain_plan}")
                except Exception as e:
                    logger.warning(f"EXPLAIN execution failed for query {idx}: {e}")

            # Validate performance if requested
            if validate_performance and indexes:
                from backend.services.performance_validator import validate_index_suggestion

                connection_string = (
                    settings.postgres_connection_string
                    if dialect == "postgres"
                    else settings.sqlite_connection_string or settings.demo_db_path
                )

                for index in indexes:
                    validation = await validate_index_suggestion(
                        query, index, dialect, connection_string
                    )
                    if validation.get("validated"):
                        # Add validation info to index suggestion
                        index.rationale += f" [Validated: {validation.get('analysis', {}).get('improvement', 'unknown')}]"

            all_indexes.extend(indexes)

            # Generate LLM rewrite if enabled
            if use_llm:
                llm_provider = get_provider()
                try:
                    rewrite = await llm_provider.propose_rewrite(schema_ddl, query, issues, dialect)
                    if rewrite:
                        rewrite.query_index = idx
                        all_rewrites.append(rewrite)
                    metrics.record_llm_call()
                except Exception as e:
                    logger.error(f"LLM rewrite failed for query {idx}: {e}")
                    metrics.record_error()

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
            metrics.record_llm_call()
        except Exception as e:
            logger.error(f"Error generating LLM explanation: {e}")
            metrics.record_error()
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
