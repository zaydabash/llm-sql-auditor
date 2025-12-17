"""Tests for the cost estimator."""

import pytest
from backend.services.analyzer.cost_estimator import estimate_cost
from backend.services.analyzer.parser import parse_query

def test_estimate_cost_full_scan_large_table():
    """Test cost estimation for full scan on large tables."""
    sql = "SELECT * FROM large_table"
    ast = parse_query(sql, dialect="sqlite")
    
    # 100k+ rows
    score, improvement = estimate_cost(ast, {"row_hints": {"large_table": 150000}}, "sqlite")
    assert score >= 50
    assert "Full scan on large table" in improvement
    
    # 10k+ rows
    score, improvement = estimate_cost(ast, {"row_hints": {"large_table": 15000}}, "sqlite")
    assert score >= 30
    assert "Full scan on table" in improvement

def test_estimate_cost_cross_join():
    """Test cost estimation for CROSS JOIN."""
    sql = "SELECT * FROM t1 CROSS JOIN t2"
    ast = parse_query(sql, dialect="sqlite")
    score, improvement = estimate_cost(ast, {}, "sqlite")
    assert score >= 40
    assert "Potential cartesian product" in improvement

def test_estimate_cost_correlated_subquery():
    """Test cost estimation for correlated subqueries."""
    # EXISTS
    sql_exists = "SELECT * FROM t1 WHERE EXISTS (SELECT 1 FROM t2 WHERE t2.id = t1.id)"
    ast_exists = parse_query(sql_exists, dialect="sqlite")
    score, improvement = estimate_cost(ast_exists, {}, "sqlite")
    assert score >= 30
    assert "Correlated subquery" in improvement
    
    # IN with dot (correlated)
    sql_in = "SELECT * FROM t1 WHERE id IN (SELECT t2.id FROM t2 WHERE t2.ref = t1.id)"
    ast_in = parse_query(sql_in, dialect="sqlite")
    score, improvement = estimate_cost(ast_in, {}, "sqlite")
    assert score >= 30
    assert "Correlated subquery" in improvement

def test_estimate_cost_offset():
    """Test cost estimation for large OFFSET."""
    sql = "SELECT * FROM t1 LIMIT 10 OFFSET 1000"
    ast = parse_query(sql, dialect="sqlite")
    score, improvement = estimate_cost(ast, {}, "sqlite")
    assert score >= 15
    assert "Large OFFSET detected" in improvement

def test_estimate_cost_well_optimized():
    """Test cost estimation for well-optimized query."""
    sql = "SELECT id FROM t1 WHERE id = 1"
    ast = parse_query(sql, dialect="sqlite")
    score, improvement = estimate_cost(ast, {}, "sqlite")
    assert score < 15
    assert "well-optimized" in improvement
