"""Tests for the rules engine."""

import pytest
from backend.services.analyzer.rules_engine import run_all_rules
from backend.services.analyzer.parser import parse_query


def test_run_all_rules_select_star():
    """Test SELECT * rule."""
    sql = "SELECT * FROM users"
    ast = parse_query(sql, dialect="postgres")
    issues = run_all_rules(ast, 0, {"tables": {}, "row_hints": {}})
    
    assert any(i.code == "R001" for i in issues)


def test_run_all_rules_leading_wildcard():
    """Test leading wildcard rule."""
    sql = "SELECT name FROM users WHERE name LIKE '%abc'"
    ast = parse_query(sql, dialect="postgres")
    issues = run_all_rules(ast, 0, {"tables": {}, "row_hints": {}})
    
    assert any(i.code == "R009" for i in issues)


def test_run_all_rules_function_in_where():
    """Test function in WHERE rule."""
    sql = "SELECT * FROM users WHERE LOWER(email) = 'test'"
    ast = parse_query(sql, dialect="postgres")
    issues = run_all_rules(ast, 0, {"tables": {}, "row_hints": {}})
    
    assert any(i.code == "R004" for i in issues)


def test_run_all_rules_no_issues():
    """Test query with no issues."""
    sql = "SELECT id, name FROM users WHERE id = 1"
    ast = parse_query(sql, dialect="postgres")
    issues = run_all_rules(ast, 0, {"tables": {}, "row_hints": {}})
    
    # Might still have some info level issues, but should be clean of major ones
    assert not any(i.severity == "error" for i in issues)
