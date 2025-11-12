# Quick Start Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- Poetry (recommended) or pip
- SQLite3

## Installation Steps

1. **Clone and navigate to the project**
   ```bash
   cd llm-sql-auditor
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env and add OPENAI_API_KEY if you want LLM features
   ```

3. **Install Python dependencies**
   ```bash
   poetry install
   # OR
   pip install -r requirements.txt
   ```

4. **Seed the demo database**
   ```bash
   ./scripts/seed_demo.sh
   ```

5. **Start the application**

   Option A: Use the dev script
   ```bash
   ./scripts/dev_up.sh
   ```

   Option B: Manual start
   ```bash
   # Terminal 1: Backend
   poetry run uvicorn backend.app:app --reload --port 8000
   
   # Terminal 2: Frontend
   cd frontend
   npm install
   npm run dev
   ```

6. **Access the application**
   - Frontend: Available on the configured port (default: 5173)
   - API: Available on the configured port (default: 8000)
   - API Docs: Available at `/docs` endpoint

## Docker Quick Start

```bash
docker-compose up --build
```

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=backend --cov-report=html
```

## Example Usage

### Via Web UI

1. Open the frontend application in your browser
2. Paste schema DDL
3. Enter SQL queries (separate with `---`)
4. Click "Analyze Queries"

### Via API

```bash
curl -X POST <API_URL>/api/audit \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "CREATE TABLE users (id INTEGER, email TEXT);",
    "queries": ["SELECT * FROM users;"],
    "dialect": "postgres"
  }'
```

## Troubleshooting

- **Port already in use**: Change ports in `docker-compose.yml` or use different ports
- **Database not found**: Run `./scripts/seed_demo.sh`
- **LLM features not working**: Ensure `OPENAI_API_KEY` is set in `.env`
- **Frontend not connecting**: Check that backend is running on port 8000

