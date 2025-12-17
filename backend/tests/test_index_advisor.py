"""Tests for the index advisor."""

import pytest
from backend.services.analyzer.index_advisor import recommend_indexes
from backend.services.analyzer.parser import parse_query


def test_recommend_indexes_simple():
    """Test simple index suggestion."""
    sql = "SELECT * FROM users WHERE email = 'test@example.com'"
    ast = parse_query(sql, dialect="postgres")
    
    suggestions = recommend_indexes(ast, table_info={}, dialect="postgres")
    
    assert len(suggestions) > 0
    assert suggestions[0].table == "users"
    assert "email" in suggestions[0].columns


def test_recommend_indexes_join():
    """Test index suggestion for JOIN columns."""
    sql = "SELECT * FROM users u JOIN orders o ON u.id = o.user_id"
    ast = parse_query(sql, dialect="postgres")
    
    suggestions = recommend_indexes(ast, table_info={}, dialect="postgres")
    
    # Should suggest index on user_id
    cols = [c for s in suggestions for c in s.columns]
    assert "user_id" in cols


def test_recommend_indexes_composite():
    """Test composite index recommendation for WHERE + ORDER BY."""
    sql = "SELECT * FROM users WHERE status = 'active' ORDER BY created_at"
    ast = parse_query(sql, dialect="postgres")
    suggestions = recommend_indexes(ast, {}, "postgres")
    
    # Should suggest a composite index
    composite = next((s for s in suggestions if s.table == "users" and len(s.columns) > 1), None)
    assert composite is not None
    assert "status" in composite.columns
    assert "created_at" in composite.columns



def test_recommend_indexes_order_by():
    """Test index recommendation for ORDER BY."""
    sql = "SELECT * FROM users ORDER BY created_at DESC"
    ast = parse_query(sql, dialect="postgres")
    suggestions = recommend_indexes(ast, {}, "postgres")
    
    assert any(s.table == "users" and "created_at" in s.columns for s in suggestions)


def test_recommend_indexes_group_by():
    """Test index recommendation for GROUP BY."""
    sql = "SELECT status, COUNT(*) FROM orders GROUP BY status"
    ast = parse_query(sql, dialect="postgres")
    suggestions = recommend_indexes(ast, {}, "postgres")
    
    assert any(s.table == "orders" and "status" in s.columns for s in suggestions)


def test_recommend_indexes_like_gin():
    """Test GIN index recommendation for LIKE with leading wildcard in Postgres."""
    sql = "SELECT * FROM users WHERE email LIKE '%@gmail.com'"
    ast = parse_query(sql, dialect="postgres")
    suggestions = recommend_indexes(ast, {}, "postgres")
    print(f"DEBUG: suggestions={suggestions}")
    assert any(s.table == "users" and "email" in s.columns and s.type == "gin" for s in suggestions)



def test_recommend_indexes_complex_expressions():
    """Test index recommendation for complex WHERE expressions."""
    # IN clause
    sql_in = "SELECT * FROM users WHERE id IN (1, 2, 3)"
    ast_in = parse_query(sql_in, dialect="sqlite")
    suggestions_in = recommend_indexes(ast_in, {}, "sqlite")
    assert any("id" in s.columns for s in suggestions_in)
    
    # BETWEEN clause
    sql_bet = "SELECT * FROM users WHERE age BETWEEN 18 AND 30"
    ast_bet = parse_query(sql_bet, dialect="sqlite")
    suggestions_bet = recommend_indexes(ast_bet, {}, "sqlite")
    assert any("age" in s.columns for s in suggestions_bet)
    
    # Subquery
    sql_sub = "SELECT * FROM users WHERE id = (SELECT user_id FROM orders LIMIT 1)"
    ast_sub = parse_query(sql_sub, dialect="sqlite")
    suggestions_sub = recommend_indexes(ast_sub, {}, "sqlite")
    assert any("id" in s.columns for s in suggestions_sub)
    
    # EXISTS
    sql_exists = "SELECT * FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)"
    ast_exists = parse_query(sql_exists, dialect="sqlite")
    suggestions_exists = recommend_indexes(ast_exists, {}, "sqlite")
    assert any("id" in s.columns for s in suggestions_exists)


def test_recommend_indexes_join_using():
    """Test index recommendation for JOIN with USING clause."""
    sql = "SELECT * FROM users JOIN orders USING (user_id)"
    ast = parse_query(sql, dialect="postgres")
    suggestions = recommend_indexes(ast, {}, "postgres")
    assert any("user_id" in s.columns for s in suggestions)


def test_recommend_indexes_order_group_identifiers():
    """Test index recommendation for ORDER BY and GROUP BY with identifiers."""
    sql = "SELECT name, count(*) FROM users GROUP BY name ORDER BY name"
    ast = parse_query(sql, dialect="sqlite")
    suggestions = recommend_indexes(ast, {}, "sqlite")
    assert any("name" in s.columns for s in suggestions)


def test_recommend_indexes_no_where():
    """Test index suggestion with no WHERE clause."""
    sql = "SELECT * FROM users"
    ast = parse_query(sql, dialect="postgres")
    
    suggestions = recommend_indexes(ast, table_info={}, dialect="postgres")
    assert len(suggestions) == 0
