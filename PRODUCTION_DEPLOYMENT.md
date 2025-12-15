# Production Deployment Guide

## Overview

This guide covers deploying SQL Auditor to production with all security and performance features enabled.

## Prerequisites

- Docker and Docker Compose
- PostgreSQL (optional, for EXPLAIN features)
- Domain name with SSL certificate
- OpenAI API key (for LLM features)

## Quick Start

1. **Clone and configure**:
   ```bash
   git clone <repo>
   cd llm-sql-auditor
   cp .env.production.example .env.production
   # Edit .env.production with your values
   ```

2. **Generate API key**:
   ```python
   from backend.core.auth import generate_api_key
   print(generate_api_key())
   ```

3. **Deploy**:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Configuration

### Environment Variables

See `.env.production.example` for all available options.

**Required for production**:
- `API_KEY`: Secure API key for authentication
- `REQUIRE_AUTH=true`: Enable API key authentication
- `CORS_ORIGINS`: Your frontend domain(s)

**Optional**:
- `ENABLE_EXPLAIN=true`: Enable EXPLAIN plan execution
- `POSTGRES_CONNECTION_STRING`: For PostgreSQL EXPLAIN
- `SQLITE_CONNECTION_STRING`: For SQLite EXPLAIN

### Security Settings

```bash
# Enable authentication
SQLAUDITOR_REQUIRE_AUTH=true
SQLAUDITOR_API_KEY=your-secure-key-here

# Configure CORS
SQLAUDITOR_CORS_ORIGINS=https://yourdomain.com

# Rate limiting (default: 10/minute)
SQLAUDITOR_RATE_LIMIT_PER_MINUTE=10
```

## Features

### Authentication

All API endpoints require the `X-API-Key` header when `REQUIRE_AUTH=true`:

```bash
curl -H "X-API-Key: your-key" https://api.yourdomain.com/api/audit \
  -H "Content-Type: application/json" \
  -d '{"schema": "...", "queries": ["..."], "dialect": "postgres"}'
```

### EXPLAIN Integration

Enable real EXPLAIN plan execution:

```bash
SQLAUDITOR_ENABLE_EXPLAIN=true
SQLAUDITOR_POSTGRES_CONNECTION_STRING=postgresql://user:pass@host:5432/db
```

This will:
- Execute EXPLAIN queries against your database
- Validate index suggestions
- Provide real performance metrics

### Performance Validation

Enable performance validation to test index suggestions:

```python
# In your API calls, set validate_performance=True
response = await audit_queries(
    schema_ddl=schema,
    queries=queries,
    dialect="postgres",
    validate_performance=True,
)
```

## Monitoring

### Health Check

```bash
curl https://api.yourdomain.com/api/health
```

Returns:
```json
{
  "ok": true,
  "metrics": {
    "queries_audited": 1234,
    "errors_occurred": 5,
    "llm_calls": 890,
    "average_audit_time": 1.23
  },
  "version": "0.1.0"
}
```

### Logging

Logs are output to stdout/stderr. Configure log level:

```bash
SQLAUDITOR_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

## Scaling

### Horizontal Scaling

The backend is stateless and can be scaled horizontally:

```yaml
# docker-compose.prod.yml
services:
  backend:
    deploy:
      replicas: 3
```

### Database Connections

For EXPLAIN features, use connection pooling:

```python
# PostgreSQL connection string with pooling
POSTGRES_CONNECTION_STRING=postgresql://user:pass@host:5432/db?pool_size=10
```

## Security Checklist

- [ ] API key authentication enabled
- [ ] CORS configured with specific origins
- [ ] Rate limiting enabled
- [ ] Input validation enabled
- [ ] Error messages sanitized
- [ ] HTTPS/TLS enabled
- [ ] Database connections secured
- [ ] API keys rotated regularly

## Troubleshooting

### Authentication Issues

If you get 401 errors:
1. Check `REQUIRE_AUTH` is set correctly
2. Verify API key in request header
3. Check API key matches configured key

### EXPLAIN Not Working

If EXPLAIN plans aren't generated:
1. Verify `ENABLE_EXPLAIN=true`
2. Check connection string is valid
3. Ensure database is accessible
4. Check logs for connection errors

### Performance Issues

If queries are slow:
1. Check database connection pool size
2. Monitor LLM API rate limits
3. Review query complexity
4. Check EXPLAIN plan execution time

## Backup and Recovery

### Audit History

Audit history is stored in SQLite by default:

```bash
# Backup
cp backend/db/audit_history.sqlite backup.sqlite

# Restore
cp backup.sqlite backend/db/audit_history.sqlite
```

### Configuration

Backup your `.env.production` file securely.

## Updates

1. Pull latest code
2. Rebuild containers: `docker-compose -f docker-compose.prod.yml build`
3. Restart: `docker-compose -f docker-compose.prod.yml up -d`

## Support

For issues or questions:
- Check logs: `docker-compose -f docker-compose.prod.yml logs`
- Review health endpoint metrics
- Check GitHub issues

