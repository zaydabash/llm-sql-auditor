"""Tests for the audit pipeline."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.services.pipeline import audit_queries
from backend.core.models import AuditResponse, Issue, Summary


@pytest.mark.asyncio
async def test_audit_queries_success():
    """Test successful audit pipeline execution."""
    schema = "CREATE TABLE t1 (id INT);"
    queries = ["SELECT * FROM t1;"]
    
    # Mock the internal components
    with patch("backend.services.pipeline.parse_schema") as mock_parse_schema, \
         patch("backend.services.pipeline.extract_table_info") as mock_extract_info, \
         patch("backend.services.pipeline.parse_query") as mock_parse_query, \
         patch("backend.services.pipeline.run_all_rules") as mock_run_rules, \
         patch("backend.services.pipeline.estimate_cost") as mock_estimate_cost, \
         patch("backend.services.pipeline.recommend_indexes") as mock_recommend:
        
        mock_parse_schema.return_value = MagicMock()
        mock_extract_info.return_value = {"tables": {}, "row_hints": {}}
        mock_parse_query.return_value = MagicMock()
        mock_run_rules.return_value = [Issue(code="W001", severity="warn", message="Test", rule="RULE", query_index=0)]
        mock_estimate_cost.return_value = (20, "Minor improvement")
        mock_recommend.return_value = []
        
        response = await audit_queries(schema, queries, dialect="sqlite", use_llm=False)
        
        assert isinstance(response, AuditResponse)
        assert len(response.issues) == 1
        assert response.summary.total_issues == 1


@pytest.mark.asyncio
async def test_audit_queries_with_llm():
    """Test audit pipeline with LLM enabled."""
    schema = "CREATE TABLE t1 (id INT);"
    queries = ["SELECT * FROM t1;"]
    
    mock_provider = MagicMock()
    mock_provider.generate_explanation = AsyncMock(return_value="AI Explanation")
    mock_provider.propose_rewrite = AsyncMock(return_value=None)

    with patch("backend.services.pipeline.get_provider", return_value=mock_provider), \
         patch("backend.services.pipeline.parse_query", return_value=MagicMock()), \
         patch("backend.services.pipeline.run_all_rules", return_value=[]), \
         patch("backend.services.pipeline.estimate_cost", return_value=(0, "Optimized")), \
         patch("backend.services.pipeline.recommend_indexes", return_value=[]):
        
        response = await audit_queries(schema, queries, dialect="sqlite", use_llm=True)
        
        assert response.llm_explain == "AI Explanation"


@pytest.mark.asyncio
async def test_audit_queries_with_performance_validation():
    """Test audit pipeline with performance validation enabled."""
    schema = "CREATE TABLE t1 (id INT);"
    queries = ["SELECT * FROM t1"]
    
    with patch("backend.services.pipeline.validate_index_suggestion") as mock_validate:
        mock_validate.return_value = {
            "validated": True,
            "speedup": 2.5,
            "timing_before_ms": 10.0,
            "timing_after_ms": 4.0
        }
        
        # We need to ensure index_advisor returns something to trigger validation
        with patch("backend.services.pipeline.recommend_indexes") as mock_recommend:
            from backend.core.models import IndexSuggestion
            mock_recommend.return_value = [
                IndexSuggestion(table="t1", columns=["id"], rationale="test")
            ]
            
            response = await audit_queries(schema, queries, "sqlite", use_llm=False, validate_performance=True)
            
            assert response.summary.total_issues >= 0
            assert len(response.indexes) > 0
            # The validation result should be attached to the index suggestion or handled
            mock_validate.assert_called()


@pytest.mark.asyncio
async def test_audit_queries_invalid_sql():
    """Test audit pipeline with invalid SQL."""
    schema = "CREATE TABLE t1 (id INT);"
    queries = ["INVALID SQL"]
    
    # Should not crash, but return error or empty issues
    response = await audit_queries(schema, queries, "sqlite", use_llm=False)
    assert response.summary.total_issues == 0
    assert len(response.issues) == 0


@pytest.mark.asyncio
async def test_audit_queries_empty_input():
    """Test audit pipeline with empty input."""
    response = await audit_queries("", [], "sqlite", use_llm=False)
    assert response.summary.total_issues == 0
    assert len(response.issues) == 0


@pytest.mark.asyncio
async def test_audit_queries_error_handling():
    """Test pipeline error handling for invalid queries."""
    schema = "CREATE TABLE t1 (id INT);"
    queries = ["INVALID SQL"]
    
    with patch("backend.services.pipeline.parse_query") as mock_parse_query:
        mock_parse_query.side_effect = Exception("Parse error")
        
        response = await audit_queries(schema, queries, dialect="sqlite", use_llm=False)
        
        assert len(response.issues) == 1
        assert response.issues[0].code == "PARSE_ERROR"
