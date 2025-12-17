from backend.services.analyzer.index_advisor import recommend_indexes
from backend.services.analyzer.parser import parse_query

sql = "SELECT * FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)"
ast = parse_query(sql, dialect="sqlite")
suggestions = recommend_indexes(ast, {}, "sqlite")

print(f"Tables: {ast.get_referenced_tables()}")
print(f"Aliases: {ast.get_table_aliases()}")
print(f"Suggestions: {suggestions}")

sql_complex = "SELECT * FROM users WHERE id IN (1, 2) AND age BETWEEN 18 AND 30"
ast_complex = parse_query(sql_complex, dialect="sqlite")
where = ast_complex.get_where_predicates()[0]
condition = where.this
print(f"Condition type: {type(condition)}")
if hasattr(condition, "left"): print(f"Left type: {type(condition.left)}")
if hasattr(condition, "right"): print(f"Right type: {type(condition.right)}")

from backend.services.analyzer.index_advisor import _extract_where_columns_ast
cols = _extract_where_columns_ast(ast_complex)
print(f"Extracted cols: {cols}")



