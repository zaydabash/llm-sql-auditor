"""Minimal command-line demo of the SQL Auditor analysis pipeline.

Run with:
    python -m backend.scripts.demo
"""

import asyncio

from backend.services.pipeline import audit_queries

SCHEMA = (
    "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);\n"
    "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, "
    "created_at TEXT, total_cents INTEGER);"
)

QUERY = (
    "SELECT * FROM orders o JOIN users u ON u.id = o.user_id "
    "WHERE LOWER(u.email) = 'admin@example.com' ORDER BY o.created_at DESC;"
)


async def main() -> None:
    response = await audit_queries(
        schema_ddl=SCHEMA,
        queries=[QUERY],
        dialect="postgres",
        use_llm=False,
    )

    print(f"Query: {QUERY}\n")

    print("Issues:")
    for issue in response.issues:
        rule = issue.rule or ""
        message = issue.message.split(".")[0].split(" - ")[0]
        print(f"  [{issue.code}] {issue.severity.upper():5} {rule:18} {message}")

    print("\nSummary:")
    print(
        f"  totalIssues={response.summary.total_issues}  "
        f"highSeverity={response.summary.high_severity}"
    )
    if response.summary.est_improvement:
        print(f"  estImprovement={response.summary.est_improvement.split(' - ')[0]}")

    print("\nRecommended indexes:")
    sorted_indexes = sorted(response.indexes, key=lambda i: (i.table, i.columns))
    for index in sorted_indexes:
        columns = ", ".join(index.columns)
        print(f"  CREATE INDEX ON {index.table} ({columns})  -- {index.rationale.split('.')[0]}")


if __name__ == "__main__":
    asyncio.run(main())
