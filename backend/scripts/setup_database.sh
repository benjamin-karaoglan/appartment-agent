#!/bin/bash
# Database setup script - Run migrations and import DVF data

set -e  # Exit on error

echo "=== Database Setup Script ==="
echo ""

# Step 1: Wait for database to be ready
echo "Step 1: Waiting for database to be ready..."
until PGPASSWORD=appartment psql -h localhost -U appartment -d appartment_agent -c '\q' 2>/dev/null; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done
echo "✓ Database is ready"
echo ""

# Step 2: Run Alembic migrations
echo "Step 2: Running Alembic migrations..."
cd /app
alembic upgrade head
echo "✓ Migrations complete"
echo ""

# Step 3: Create test user (skip if exists)
echo "Step 3: Creating test user..."
python -c "
from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

db = SessionLocal()
try:
    existing = db.query(User).filter(User.email == 'test@example.com').first()
    if not existing:
        user = User(
            email='test@example.com',
            hashed_password=get_password_hash('test123'),
            full_name='Test User',
            is_active=True
        )
        db.add(user)
        db.commit()
        print('✓ Test user created (email: test@example.com, password: test123)')
    else:
        print('✓ Test user already exists')
finally:
    db.close()
"
echo ""

# Step 4: Import DVF data
echo "Step 4: Importing DVF data..."
if [ -d "/app/data/dvf" ] && [ "$(ls -A /app/data/dvf/*.txt 2>/dev/null)" ]; then
    echo "Found DVF files:"
    ls -lh /app/data/dvf/*.txt
    echo ""
    echo "Starting import (this may take several minutes)..."
    timeout 600 python scripts/import_dvf_chunked.py
    echo "✓ DVF data import complete"
else
    echo "⚠ No DVF files found in /app/data/dvf/"
    echo "Please add DVF files and run: docker-compose exec backend python scripts/import_dvf_chunked.py"
fi
echo ""

echo "=== Database Setup Complete ==="
echo ""
echo "You can now:"
echo "  - Access frontend: http://localhost:3000"
echo "  - Login with: test@example.com / test123"
echo "  - Access Temporal UI: http://localhost:8088"
echo "  - Access MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
