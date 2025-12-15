"""Tests for rules engine."""

import pytest

from backend.services.analyzer.parser import parse_query
from backend.services.analyzer.rules_engine import (
    check_agg_no_grouping_index,
    check_like_prefix_wildcard,
    check_missing_predicate,
    check_non_sargable,
    check_order_by_no_index,
    check_select_star,
    run_all_rules,
)


@pytest.fixture
def sample_table_info():
    """Sample table info for testing."""
    return {
        "tables": {
            "users": {"columns": [{"name": "id", "type": "INTEGER"}]},
            "orders": {"columns": [{"name": "id", "type": "INTEGER"}]},
        },
        "row_hints": {"users": 50000, "orders": 100000},
    }


def test_check_select_star():
    """Test R001: SELECT * detection."""
    query = "SELECT * FROM users;"
    query_ast = parse_query(query, "postgres")
    issues = check_select_star(query_ast, 0)

    assert len(issues) == 1
    assert issues[0].code == "R001"
    assert issues[0].severity == "warn"

    # Should not trigger on explicit columns
    query2 = "SELECT id, email FROM users;"
    query_ast2 = parse_query(query2, "postgres")
    issues2 = check_select_star(query_ast2, 0)
    assert len(issues2) == 0


def test_check_non_sargable():
    """Test R004: Non-SARGable predicate detection."""
    query = "SELECT * FROM users WHERE LOWER(email) = 'test@example.com';"
    query_ast = parse_query(query, "postgres")
    issues = check_non_sargable(query_ast, 0)

    assert len(issues) > 0
    assert any(issue.code == "R004" for issue in issues)


def test_check_missing_predicate(sample_table_info):
    """Test R005: Missing WHERE clause on large table."""
    query = "SELECT * FROM orders;"
    query_ast = parse_query(query, "postgres")
    issues = check_missing_predicate(query_ast, 0, sample_table_info)

    assert len(issues) > 0
    assert any(issue.code == "R005" for issue in issues)

    # Should not trigger with WHERE clause
    query2 = "SELECT * FROM orders WHERE id = 1;"
    query_ast2 = parse_query(query2, "postgres")
    issues2 = check_missing_predicate(query_ast2, 0, sample_table_info)
    assert len(issues2) == 0


def test_check_like_prefix_wildcard():
    """Test R009: LIKE with prefix wildcard."""
    query = "SELECT * FROM products WHERE name LIKE '%widget%';"
    query_ast = parse_query(query, "postgres")
    issues = check_like_prefix_wildcard(query_ast, 0)

    assert len(issues) > 0
    assert any(issue.code == "R009" for issue in issues)


def test_check_order_by_no_index():
    """Test R006: ORDER BY without index."""
    query = "SELECT * FROM orders ORDER BY created_at DESC;"
    query_ast = parse_query(query, "postgres")
    issues = check_order_by_no_index(query_ast, 0)

    assert len(issues) > 0
    assert any(issue.code == "R006" for issue in issues)


def test_check_agg_no_grouping_index():
    """Test R010: Aggregation without grouping index."""
    query = "SELECT category, COUNT(*) FROM products GROUP BY category;"
    query_ast = parse_query(query, "postgres")
    issues = check_agg_no_grouping_index(query_ast, 0)

    assert len(issues) > 0
    assert any(issue.code == "R010" for issue in issues)


def test_run_all_rules(sample_table_info):
    """Test running all rules together."""
    query = "SELECT * FROM orders WHERE LOWER(status) = 'pending' ORDER BY created_at;"
    query_ast = parse_query(query, "postgres")
    issues = run_all_rules(query_ast, 0, sample_table_info)

    assert len(issues) > 0
    # Should detect multiple issues
    codes = [issue.code for issue in issues]
    assert "R001" in codes  # SELECT *
    assert "R004" in codes  # Non-SARGable
    assert "R006" in codes  # ORDER BY
