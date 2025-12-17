import random
from locust import HttpUser, task, between

class SQLAuditorUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def audit_query(self):
        """Simulate auditing a query."""
        schema = """
        CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL);
        """
        queries = [
            "SELECT * FROM users WHERE email = 'test@example.com';",
            "SELECT u.email, SUM(o.amount) FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.email;"
        ]
        
        self.client.post("/api/audit", json={
            "schema_ddl": schema,
            "queries": queries,
            "dialect": "postgres"
        })

    @task(1)
    def health_check(self):
        """Simulate health check."""
        self.client.get("/api/health")

    @task(1)
    def get_costs(self):
        """Simulate getting costs."""
        self.client.get("/api/llm/costs")
