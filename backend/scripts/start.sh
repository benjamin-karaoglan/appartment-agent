#!/bin/bash
# Backend startup script - Initialize database then start server

set -e  # Exit on error

echo "Starting backend initialization..."

# Run database initialization
python scripts/init_db.py

# Check if initialization succeeded
if [ $? -eq 0 ]; then
    echo "Initialization complete, starting uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "Initialization failed, exiting..."
    exit 1
fi
