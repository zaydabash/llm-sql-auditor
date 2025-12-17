"""Tests for SQL dialect handling."""

import pytest
import sqlglot
from backend.core.dialects import parse_sql, parse_schema, extract_table_info


def test_parse_sql():
    """Test parsing SQL query."""
    sql = "SELECT * FROM users"
    ast = parse_sql(sql, "postgres")
    assert isinstance(ast, sqlglot.Expression)
    assert ast.key == "select"


def test_parse_schema():
    """Test parsing schema DDL."""
    ddl = "CREATE TABLE users (id INT); CREATE TABLE orders (id INT);"
    ast_list = parse_schema(ddl, "postgres")
    assert len(ast_list) == 2
    assert all(isinstance(node, sqlglot.Expression) for node in ast_list)


def test_extract_table_info_simple():
    """Test extracting table info from simple schema."""
    ddl = "CREATE TABLE users (id INT, email TEXT)"
    ast = parse_schema(ddl, "postgres")
    info = extract_table_info(ast)
    
    assert "users" in info["tables"]
    columns = info["tables"]["users"]["columns"]
    assert len(columns) == 2
    assert columns[0]["name"] == "id"
    assert columns[1]["name"] == "email"


def test_extract_table_info_with_row_hints():
    """Test extracting table info with row hints in comments."""
    ddl = """
    CREATE TABLE users (id INT);
    -- @rows=1000
    CREATE TABLE orders (id INT);
    -- @rows=5000
    """
    ast = parse_schema(ddl, "postgres")
    info = extract_table_info(ast, ddl)
    
    assert info["row_hints"].get("users") == 1000
    assert info["row_hints"].get("orders") == 5000


def test_extract_table_info_invalid_stmt():
    """Test extracting table info with non-CREATE statements."""
    ddl = "SELECT 1; CREATE TABLE users (id INT);"
    ast = parse_schema(ddl, "postgres")
    info = extract_table_info(ast)
    
    assert "users" in info["tables"]
    assert len(info["tables"]) == 1
