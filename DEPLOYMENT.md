# Deployment Guide

This guide explains how to deploy SQL Auditor to various platforms.

## Local Deployment (Docker Compose)

The easiest way to run SQL Auditor locally with full monitoring:

```bash
docker-compose up --build
```

- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Prometheus**: [http://localhost:9090](http://localhost:9090)
- **Grafana**: [http://localhost:3000](http://localhost:3000) (Default login: `admin` / `admin`)

## Cloud Deployment

### Render (Recommended)

SQL Auditor includes a `render.yaml` blueprint for one-click deployment.

1. Fork this repository.
2. Connect your GitHub account to [Render](https://render.com).
3. Click **New** -> **Blueprint**.
4. Select your fork.
5. Configure the `OPENAI_API_KEY` environment variable.
6. Deploy!

### Railway

1. Install the [Railway CLI](https://docs.railway.app/guides/cli).
2. Run `railway login`.
3. Run `railway link`.
4. Run `railway up`.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API Key | (Required) |
| `SQLAUDITOR_LOG_LEVEL` | Logging level (DEBUG, INFO, WARN, ERROR) | `INFO` |
| `DEFAULT_DIALECT` | Default SQL dialect (postgres, sqlite) | `postgres` |
| `SQLAUDITOR_API_KEY` | API Key for authenticating requests | (Generated) |
| `SQLAUDITOR_LLM_BUDGET_MONTHLY` | Monthly budget for LLM calls | `100.0` |

## Monitoring

SQL Auditor exports Prometheus metrics at `/metrics`. In production, you should point your Prometheus instance to this endpoint.
