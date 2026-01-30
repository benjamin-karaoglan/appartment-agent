#!/bin/bash
# Production startup script - Run migrations then start server
# Used by Cloud Run and production Docker deployments

set -e  # Exit on error

echo "=============================================="
echo "PRODUCTION STARTUP"
echo "=============================================="

# Run database migrations
echo "Running database migrations..."
python -c "
import os
import sys
from sqlalchemy import create_engine, text

db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    print('ERROR: DATABASE_URL not set')
    sys.exit(1)

# Mask password for logging
masked = db_url
if '@' in db_url:
    parts = db_url.split('@')
    user_part = parts[0].rsplit(':', 1)
    if len(user_part) == 2:
        masked = f'{user_part[0]}:***@{\"@\".join(parts[1:])}'
print(f'Database URL: {masked}')

# Test connection
print('Testing database connection...')
try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print(f'Connection successful!')
except Exception as e:
    print(f'ERROR: Database connection failed: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "ERROR: Database connection test failed"
    exit 1
fi

# Run Alembic migrations
echo "Running Alembic migrations..."
alembic upgrade head

if [ $? -ne 0 ]; then
    echo "ERROR: Alembic migrations failed"
    exit 1
fi

echo "=============================================="
echo "Migrations complete, starting uvicorn..."
echo "=============================================="

# Start uvicorn (exec replaces shell process)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
