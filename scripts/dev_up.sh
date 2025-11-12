#!/bin/bash
# Development startup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Starting SQL Auditor development environment..."

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "Creating .env from .env.example..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

# Seed database if it doesn't exist
if [ ! -f "$PROJECT_ROOT/backend/db/demo.sqlite" ]; then
    echo "Seeding demo database..."
    "$PROJECT_ROOT/scripts/seed_demo.sh"
fi

# Install Python dependencies if needed
if [ ! -d "$PROJECT_ROOT/.venv" ] && [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "Installing Python dependencies..."
    cd "$PROJECT_ROOT"
    if command -v poetry &> /dev/null; then
        poetry install
    else
        echo "Poetry not found. Please install dependencies manually:"
        echo "  pip install -r requirements.txt"
    fi
fi

# Install frontend dependencies if needed
if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd "$PROJECT_ROOT/frontend"
    npm install
fi

echo ""
echo "Starting services..."
echo "Backend will run on http://localhost:8000"
echo "Frontend will run on http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start backend in background
cd "$PROJECT_ROOT"
if command -v poetry &> /dev/null; then
    poetry run uvicorn backend.app:app --reload --port 8000 &
else
    python -m uvicorn backend.app:app --reload --port 8000 &
fi
BACKEND_PID=$!

# Start frontend in background
cd "$PROJECT_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

# Wait for user interrupt
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait

