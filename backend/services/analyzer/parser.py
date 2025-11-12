"""SQL parsing utilities."""

from typing import Literal

import sqlglot
from sqlglot import expressions

from backend.core.dialects import parse_sql


class QueryAST:
    """Wrapper around SQLGlot AST with helper methods."""

    def __init__(self, ast: sqlglot.Expression, query: str, dialect: Literal["postgres", "sqlite"]):
        self.ast = ast
        self.query = query
        self.dialect = dialect

    def get_select_star(self) -> list[expressions.Star]:
        """Find all SELECT * occurrences."""
        return list(self.ast.find_all(expressions.Star))

    def get_joins(self) -> list[expressions.Join]:
        """Get all JOIN expressions."""
        return list(self.ast.find_all(expressions.Join))

    def get_where_predicates(self) -> list[expressions.Where]:
        """Get WHERE clauses."""
        return list(self.ast.find_all(expressions.Where))

    def get_order_by(self) -> list[expressions.Order]:
        """Get ORDER BY clauses."""
        return list(self.ast.find_all(expressions.Order))

    def get_distinct(self) -> list[expressions.Distinct]:
        """Get DISTINCT clauses."""
        return list(self.ast.find_all(expressions.Distinct))

    def get_like_expressions(self) -> list[expressions.Like]:
        """Get LIKE expressions."""
        return list(self.ast.find_all(expressions.Like))

    def get_aggregations(self) -> list[expressions.AggFunc]:
        """Get aggregation functions."""
        return list(self.ast.find_all(expressions.AggFunc))

    def get_subqueries(self) -> list[expressions.Subquery]:
        """Get subqueries."""
        return list(self.ast.find_all(expressions.Subquery))

    def get_referenced_columns(self) -> set[str]:
        """Get all column references in the query."""
        columns = set()
        for col in self.ast.find_all(expressions.Column):
            table = col.table if col.table else None
            col_name = col.name if col.name else None
            if col_name:
                columns.add(f"{table}.{col_name}" if table else col_name)
        return columns

    def get_referenced_tables(self) -> set[str]:
        """Get all table references."""
        tables = set()
        for table in self.ast.find_all(expressions.Table):
            if table.name:
                tables.add(table.name)
        return tables


def parse_query(query: str, dialect: Literal["postgres", "sqlite"]) -> QueryAST:
    """Parse a SQL query into QueryAST."""
    try:
        ast = parse_sql(query, dialect)
        return QueryAST(ast, query, dialect)
    except Exception as e:
        # Return a minimal AST wrapper even on parse error
        # The rules engine can handle this gracefully
        raise ValueError(f"Failed to parse query: {e}") from e

