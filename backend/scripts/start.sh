#!/bin/bash
# Backend startup script - Initialize database then start server

set -e  # Exit on error

echo "Starting backend initialization..."

# Sync dependencies if venv is empty or incomplete (Docker volume mount case)
# Check if a key package exists to determine if sync is needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Virtual environment incomplete, syncing dependencies with UV..."
    uv sync --frozen
    echo "Dependencies synced."
fi

# Run database initialization (PATH includes .venv/bin)
python scripts/init_db.py

# Check if initialization succeeded
if [ $? -eq 0 ]; then
    echo "Initialization complete, starting uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "Initialization failed, exiting..."
    exit 1
fi
