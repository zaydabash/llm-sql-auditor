"""Benchmark SQL Auditor performance on real-world bad queries."""

import asyncio
import sqlite3
import time
from typing import List

from backend.services.pipeline import audit_queries

# 20+ Bad Query Examples
BAD_QUERIES = [
    # 1. Missing Index on JOIN
    {
        "name": "Missing Join Index",
        "schema": "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT); CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL);",
        "query": "SELECT u.name, SUM(o.amount) FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.name;",
        "rows": 10000
    },
    # 2. SELECT *
    {
        "name": "SELECT Star",
        "schema": "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, bio TEXT, large_data BLOB);",
        "query": "SELECT * FROM users WHERE id = 1;",
        "rows": 1000
    },
    # 3. Function on Column in WHERE
    {
        "name": "Function on Column",
        "schema": "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT); CREATE INDEX idx_email ON users(email);",
        "query": "SELECT * FROM users WHERE LOWER(email) = 'test@example.com';",
        "rows": 50000
    },
    # 4. Leading Wildcard LIKE
    {
        "name": "Leading Wildcard",
        "schema": "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT); CREATE INDEX idx_name ON products(name);",
        "query": "SELECT * FROM products WHERE name LIKE '%phone%';",
        "rows": 10000
    },
    # 5. N+1 Query Pattern (represented as a single query that could be optimized)
    {
        "name": "N+1 Subquery",
        "schema": "CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT); CREATE TABLE products (id INTEGER PRIMARY KEY, category_id INTEGER, name TEXT);",
        "query": "SELECT p.name, (SELECT c.name FROM categories c WHERE c.id = p.category_id) as cat_name FROM products p;",
        "rows": 5000
    },
    # 6. OR on Different Columns
    {
        "name": "OR on Different Columns",
        "schema": "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, username TEXT); CREATE INDEX idx_email ON users(email); CREATE INDEX idx_user ON users(username);",
        "query": "SELECT * FROM users WHERE email = 'test@example.com' OR username = 'testuser';",
        "rows": 10000
    },
    # 7. Unnecessary DISTINCT
    {
        "name": "Unnecessary DISTINCT",
        "schema": "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
        "query": "SELECT DISTINCT id, name FROM users WHERE id = 1;",
        "rows": 1000
    },
    # 8. Large OFFSET
    {
        "name": "Large OFFSET",
        "schema": "CREATE TABLE logs (id INTEGER PRIMARY KEY, msg TEXT, created_at TIMESTAMP); CREATE INDEX idx_created ON logs(created_at);",
        "query": "SELECT * FROM logs ORDER BY created_at DESC LIMIT 10 OFFSET 10000;",
        "rows": 50000
    },
    # 9. Implicit Type Conversion
    {
        "name": "Implicit Conversion",
        "schema": "CREATE TABLE users (id INTEGER PRIMARY KEY, phone_number TEXT); CREATE INDEX idx_phone ON users(phone_number);",
        "query": "SELECT * FROM users WHERE phone_number = 1234567890;",
        "rows": 10000
    },
    # 10. Correlated Subquery
    {
        "name": "Correlated Subquery",
        "schema": "CREATE TABLE employees (id INTEGER PRIMARY KEY, dept_id INTEGER, salary REAL);",
        "query": "SELECT * FROM employees e1 WHERE salary > (SELECT AVG(salary) FROM employees e2 WHERE e2.dept_id = e1.dept_id);",
        "rows": 5000
    },
    # Add 10 more to reach 20+
    {"name": "Cartesian Product", "schema": "CREATE TABLE t1 (id INT); CREATE TABLE t2 (id INT);", "query": "SELECT * FROM t1, t2;", "rows": 100},
    {"name": "NOT IN with NULLs", "schema": "CREATE TABLE t1 (id INT);", "query": "SELECT * FROM t1 WHERE id NOT IN (SELECT id FROM t1 WHERE id IS NULL);", "rows": 1000},
    {"name": "ORDER BY Non-Indexed", "schema": "CREATE TABLE t1 (id INT, val TEXT);", "query": "SELECT * FROM t1 ORDER BY val LIMIT 10;", "rows": 10000},
    {"name": "Large IN Clause", "schema": "CREATE TABLE t1 (id INT PRIMARY KEY);", "query": f"SELECT * FROM t1 WHERE id IN ({','.join(map(str, range(1000)))});", "rows": 10000},
    {"name": "GROUP BY on Large Text", "schema": "CREATE TABLE t1 (id INT, long_text TEXT);", "query": "SELECT long_text, COUNT(*) FROM t1 GROUP BY long_text;", "rows": 5000},
    {"name": "HAVING without GROUP BY", "schema": "CREATE TABLE t1 (id INT);", "query": "SELECT COUNT(*) FROM t1 HAVING COUNT(*) > 0;", "rows": 1000},
    {"name": "UNION instead of UNION ALL", "schema": "CREATE TABLE t1 (id INT);", "query": "SELECT id FROM t1 UNION SELECT id FROM t1;", "rows": 5000},
    {"name": "Redundant Joins", "schema": "CREATE TABLE t1 (id INT PRIMARY KEY); CREATE TABLE t2 (id INT PRIMARY KEY, t1_id INT REFERENCES t1(id));", "query": "SELECT t2.* FROM t2 JOIN t1 ON t2.t1_id = t1.id;", "rows": 5000},
    {"name": "Case Insensitive Search", "schema": "CREATE TABLE t1 (val TEXT);", "query": "SELECT * FROM t1 WHERE val LIKE 'abc%';", "rows": 10000},
    {"name": "Inefficient Paging", "schema": "CREATE TABLE t1 (id INT PRIMARY KEY);", "query": "SELECT * FROM t1 WHERE id > 1000 LIMIT 10;", "rows": 50000}
]

async def run_benchmark():
    print(f"{'Benchmark Name':<30} | {'Issues':<8} | {'Improvement':<15}")
    print("-" * 60)
    
    total_issues = 0
    total_improvements = 0
    
    for test in BAD_QUERIES:
        try:
            start_time = time.time()
            response = await audit_queries(
                schema_ddl=test["schema"],
                queries=[test["query"]],
                dialect="sqlite",
                use_llm=False # Speed up benchmark
            )
            elapsed = time.time() - start_time
            
            issues_count = len(response.issues)
            improvement = response.summary.est_improvement or "None"
            
            print(f"{test['name']:<30} | {issues_count:<8} | {improvement:<15}")
            
            total_issues += issues_count
            if improvement != "None":
                total_improvements += 1
                
        except Exception as e:
            print(f"{test['name']:<30} | ERROR    | {str(e)[:20]}")

    print("-" * 60)
    print(f"Total Benchmarks: {len(BAD_QUERIES)}")
    print(f"Total Issues Found: {total_issues}")
    print(f"Benchmarks with Improvements: {total_improvements}")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
