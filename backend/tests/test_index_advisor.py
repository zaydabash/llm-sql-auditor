"""Tests for index advisor."""

import pytest

from backend.services.analyzer.index_advisor import recommend_indexes
from backend.services.analyzer.parser import parse_query


@pytest.fixture
def sample_table_info():
    """Sample table info for testing."""
    return {
        "tables": {
            "users": {"columns": [{"name": "id", "type": "INTEGER"}]},
            "orders": {"columns": [{"name": "id", "type": "INTEGER"}, {"name": "user_id", "type": "INTEGER"}]},
        },
        "row_hints": {},
    }


def test_recommend_indexes_where_clause(sample_table_info):
    """Test index recommendation for WHERE clauses."""
    query = "SELECT * FROM orders WHERE user_id = 123;"
    query_ast = parse_query(query, "postgres")
    indexes = recommend_indexes(query_ast, sample_table_info, "postgres")

    assert len(indexes) > 0
    order_indexes = [idx for idx in indexes if idx.table == "orders"]
    assert len(order_indexes) > 0
    assert "user_id" in order_indexes[0].columns


def test_recommend_indexes_join(sample_table_info):
    """Test index recommendation for JOINs."""
    query = "SELECT * FROM orders o JOIN users u ON u.id = o.user_id;"
    query_ast = parse_query(query, "postgres")
    indexes = recommend_indexes(query_ast, sample_table_info, "postgres")

    assert len(indexes) > 0
    # Should recommend index on join columns
    join_indexes = [idx for idx in indexes if "user_id" in idx.columns or "id" in idx.columns]
    assert len(join_indexes) > 0


def test_recommend_indexes_order_by(sample_table_info):
    """Test index recommendation for ORDER BY."""
    query = "SELECT * FROM orders ORDER BY created_at DESC;"
    query_ast = parse_query(query, "postgres")
    indexes = recommend_indexes(query_ast, sample_table_info, "postgres")

    assert len(indexes) > 0
    order_by_indexes = [idx for idx in indexes if idx.table == "orders"]
    assert len(order_by_indexes) > 0


def test_recommend_indexes_group_by(sample_table_info):
    """Test index recommendation for GROUP BY."""
    query = "SELECT category, COUNT(*) FROM products GROUP BY category;"
    query_ast = parse_query(query, "postgres")
    indexes = recommend_indexes(query_ast, sample_table_info, "postgres")

    assert len(indexes) > 0
    group_by_indexes = [idx for idx in indexes if "category" in idx.columns]
    assert len(group_by_indexes) > 0

