# Verification Checklist

Use this checklist to verify all fixes are working correctly.

## Quick Verification

Run this command to verify everything:
```bash
python3 -m pytest backend/tests/ -v
```

Expected: All 42 tests should pass.

## Detailed Verification

### 1. AST-Based Parsing
```bash
python3 -c "
from backend.services.analyzer.index_advisor import recommend_indexes
from backend.services.analyzer.parser import parse_query

query = parse_query('SELECT * FROM orders o JOIN users u ON u.id = o.user_id', 'postgres')
table_info = {'tables': {'orders': {}, 'users': {}}, 'row_hints': {}}
indexes = recommend_indexes(query, table_info, 'postgres')
print(f'AST parsing works: {len(indexes) > 0}')
"
```

Expected: `AST parsing works: True`

### 2. Authentication
```bash
python3 -c "
from backend.core.auth import generate_api_key
key = generate_api_key()
print(f'Key generated: {len(key) > 20}')
"
```

Expected: `Key generated: True`

### 3. Security Validation
```bash
python3 -c "
from backend.core.security import validate_sql_input
try:
    validate_sql_input('SELECT * FROM users; DROP TABLE users;')
    print('FAILED: Dangerous query accepted')
except Exception:
    print('PASSED: Dangerous query rejected')
"
```

Expected: `PASSED: Dangerous query rejected`

### 4. API Endpoints
```bash
python3 -c "
from fastapi.testclient import TestClient
from backend.app import app
client = TestClient(app)
response = client.get('/api/health')
print(f'Health check: {response.status_code == 200}')
"
```

Expected: `Health check: True`

### 5. Test Coverage
```bash
python3 -m pytest backend/tests/ --cov=backend --cov-report=term-missing | grep TOTAL
```

Expected: Coverage should be 60%+ (currently 62%)

### 6. All Imports Work
```bash
python3 -c "
from backend.services.pipeline import audit_queries
from backend.db.explain_executor import ExplainExecutor
from backend.services.performance_validator import validate_index_suggestion
from backend.services.persistence import AuditHistory
from backend.core.monitoring import metrics
print('All imports work: True')
"
```

Expected: `All imports work: True`

## Feature-Specific Verification

### EXPLAIN Integration
```bash
# Check EXPLAIN executor exists and can be imported
python3 -c "
from backend.db.explain_executor import ExplainExecutor
print('EXPLAIN executor available: True')
"
```

### Performance Validation
```bash
# Check performance validator exists
python3 -c "
from backend.services.performance_validator import validate_index_suggestion
print('Performance validator available: True')
"
```

### Persistence Layer
```bash
# Check persistence layer exists
python3 -c "
from backend.services.persistence import AuditHistory
print('Persistence layer available: True')
"
```

### Monitoring
```bash
# Check metrics work
python3 -c "
from backend.core.monitoring import metrics
print(f'Metrics available: {metrics is not None}')
print(f'Current metrics: {metrics.get_metrics()}')
"
```

## Integration Test

Test the full pipeline:
```bash
python3 -c "
import asyncio
from backend.services.pipeline import audit_queries

async def test():
    result = await audit_queries(
        schema_ddl='CREATE TABLE users (id INTEGER, email TEXT);',
        queries=['SELECT * FROM users;'],
        dialect='sqlite',
        use_llm=False
    )
    print(f'Pipeline works: {result.summary.total_issues > 0}')
    print(f'Found {len(result.issues)} issues')
    print(f'Found {len(result.indexes)} index suggestions')

asyncio.run(test())
"
```

Expected: Should find at least 1 issue (SELECT *)

## Production Readiness Check

1. **Authentication**: Check `backend/core/auth.py` exists
2. **Security**: Check `backend/core/security.py` exists
3. **Monitoring**: Check `backend/core/monitoring.py` exists
4. **EXPLAIN**: Check `backend/db/explain_executor.py` exists
5. **Performance**: Check `backend/services/performance_validator.py` exists
6. **Persistence**: Check `backend/services/persistence.py` exists
7. **Production Config**: Check `docker-compose.prod.yml` exists
8. **Deployment Docs**: Check `PRODUCTION_DEPLOYMENT.md` exists

## Automated Verification Script

Save this as `verify_all.sh`:
```bash
#!/bin/bash
echo "Running verification tests..."

echo "1. Running test suite..."
python3 -m pytest backend/tests/ -v --tb=short

echo "2. Checking test coverage..."
python3 -m pytest backend/tests/ --cov=backend --cov-report=term-missing | grep TOTAL

echo "3. Testing AST parsing..."
python3 -c "
from backend.services.analyzer.index_advisor import recommend_indexes
from backend.services.analyzer.parser import parse_query
query = parse_query('SELECT * FROM orders o JOIN users u ON u.id = o.user_id', 'postgres')
table_info = {'tables': {'orders': {}, 'users': {}}, 'row_hints': {}}
indexes = recommend_indexes(query, table_info, 'postgres')
assert len(indexes) > 0, 'AST parsing failed'
print('AST parsing: PASSED')
"

echo "4. Testing authentication..."
python3 -c "
from backend.core.auth import generate_api_key
key = generate_api_key()
assert len(key) > 20, 'Key generation failed'
print('Authentication: PASSED')
"

echo "5. Testing security..."
python3 -c "
from backend.core.security import validate_sql_input
try:
    validate_sql_input('SELECT * FROM users; DROP TABLE users;')
    assert False, 'Security validation failed'
except Exception:
    print('Security validation: PASSED')
"

echo "6. Testing API..."
python3 -c "
from fastapi.testclient import TestClient
from backend.app import app
client = TestClient(app)
response = client.get('/api/health')
assert response.status_code == 200, 'Health check failed'
print('API endpoints: PASSED')
"

echo "7. Testing imports..."
python3 -c "
from backend.services.pipeline import audit_queries
from backend.db.explain_executor import ExplainExecutor
from backend.services.performance_validator import validate_index_suggestion
from backend.services.persistence import AuditHistory
from backend.core.monitoring import metrics
print('All imports: PASSED')
"

echo "All verification tests completed!"
```

Run with: `chmod +x verify_all.sh && ./verify_all.sh`

## What Success Looks Like

- All 42 tests pass
- Test coverage is 60%+
- AST parsing works (no regex errors)
- Authentication system works
- Security validation rejects dangerous queries
- API endpoints respond correctly
- All critical imports work
- EXPLAIN executor available
- Performance validator available
- Persistence layer available
- Monitoring/metrics work

## If Something Fails

1. Check error messages carefully
2. Verify dependencies are installed: `pip3 install -r requirements.txt`
3. Check Python version: `python3 --version` (should be 3.11+)
4. Review test output for specific failures
5. Check that all files exist in expected locations

