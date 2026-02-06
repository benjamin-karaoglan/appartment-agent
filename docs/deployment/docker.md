# Docker Deployment

Deploy AppArt Agent locally using Docker Compose.

## Overview

The Docker Compose configuration provides a complete local development and testing environment.

### Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `frontend` | Custom (pnpm) | 3000 | Next.js application |
| `backend` | Custom (UV) | 8000 | FastAPI application |
| `db` | postgres:15-alpine | 5432 | PostgreSQL database |
| `redis` | redis:7-alpine | 6379 | Caching |
| `minio` | minio/minio:latest | 9000, 9001 | Object storage |
| `minio-setup` | minio/mc:latest | - | Bucket initialization |

## Quick Start

```bash
# Clone repository
git clone https://github.com/benjamin-karaoglan/appart-agent.git
cd appart-agent

# Configure environment
cp .env.example .env
# Add GOOGLE_CLOUD_API_KEY to .env

# Start services
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Verify
docker-compose ps
```

## Configuration

### docker-compose.yml

Key configuration sections:

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: dev              # Use dev target for hot-reload
    environment:
      DATABASE_URL: postgresql://appart:appart@db:5432/appart_agent
      GOOGLE_CLOUD_API_KEY: ${GOOGLE_CLOUD_API_KEY}
      MINIO_ENDPOINT: minio:9000
    volumes:
      - ./backend:/app         # Mount source for hot-reload
    depends_on:
      db:
        condition: service_healthy
```

### Environment Variables

Create `.env` in project root (backend):

```bash
# Required
GOOGLE_CLOUD_API_KEY=your_api_key
SECRET_KEY=your-secret-key-32-chars-minimum

# Optional
GOOGLE_CLOUD_PROJECT=your-project
GEMINI_USE_VERTEXAI=false
AUTO_IMPORT_DVF=false
```

Create `frontend/.env.local` (frontend):

```bash
# Required
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
DATABASE_URL=postgresql://appart:appart@localhost:5432/appart_agent
BETTER_AUTH_SECRET=your-secret-at-least-32-chars

# Optional — Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## Building Images

### Development Build

```bash
# Build all services
docker-compose build

# Build specific service
docker-compose build backend

# Build with no cache
docker-compose build --no-cache backend
```

### Production Build

```bash
# Build production images
docker-compose -f docker-compose.yml build \
  --build-arg TARGET=production
```

### Multi-Stage Dockerfiles

Backend Dockerfile targets:

```dockerfile
# Development - includes dev dependencies
FROM python-base as dev
RUN uv pip install -e ".[dev]"
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0"]

# Production - minimal image
FROM python-base as production
RUN uv pip install .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

## Service Management

### Start Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d backend

# Start with logs visible
docker-compose up
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (caution: deletes data)
docker-compose down -v

# Stop specific service
docker-compose stop backend
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart backend
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail 100 backend
```

## Database Operations

### Run Migrations

```bash
docker-compose exec backend alembic upgrade head
```

### Access Database

```bash
# psql shell
docker-compose exec db psql -U appart -d appart_agent

# Run SQL command
docker-compose exec db psql -U appart -d appart_agent -c "SELECT COUNT(*) FROM dvf_records;"
```

### Backup Database

```bash
# Create backup
docker-compose exec db pg_dump -U appart appart_agent > backup.sql

# Restore backup
docker-compose exec -T db psql -U appart appart_agent < backup.sql
```

## Object Storage (MinIO)

### Access Console

- URL: http://localhost:9001
- Username: `minioadmin`
- Password: `minioadmin`

### MinIO CLI

```bash
# Configure mc client
docker-compose exec minio-setup mc alias set local http://minio:9000 minioadmin minioadmin

# List buckets
docker-compose exec minio-setup mc ls local/

# List files in bucket
docker-compose exec minio-setup mc ls local/documents/
```

## Development Workflow

### Using dev.sh Script

```bash
# Start services
./dev.sh start

# View logs
./dev.sh logs
./dev.sh logs backend

# Restart service
./dev.sh restart backend

# Stop services
./dev.sh stop

# Open shell in container
./dev.sh shell backend

# Rebuild service
./dev.sh rebuild backend
```

### Hot Reload

Both backend and frontend support hot reload in development:

| Change | Reload Time |
|--------|-------------|
| Python (.py) | ~1 second |
| React (.tsx) | < 1 second |
| Tailwind (CSS) | Instant |

## Resource Requirements

### Minimum Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4 GB | 8 GB |
| CPU | 2 cores | 4 cores |
| Disk | 10 GB | 20 GB |

### Resource Limits

Set in docker-compose.yml:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs backend

# Check container status
docker-compose ps

# Inspect container
docker inspect appart-agent-backend-1
```

### Database Connection Failed

```bash
# Verify database is running
docker-compose ps db

# Check database logs
docker-compose logs db

# Test connection
docker-compose exec db pg_isready -U appart
```

### Port Already in Use

```bash
# Find process using port
lsof -i :3000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
ports:
  - "3001:3000"  # Map to different host port
```

### Out of Disk Space

```bash
# Remove unused containers, networks, images
docker system prune -a

# Remove unused volumes (caution: deletes data)
docker volume prune
```

## Production Considerations

For production deployment, consider:

1. **Use production targets** in Dockerfiles
2. **Configure proper secrets** (not .env files)
3. **Set up proper logging** and monitoring
4. **Configure backups** for database and storage
5. **Use cloud-managed services** for scalability

See [GCP Deployment](gcp.md) for production deployment guide.
