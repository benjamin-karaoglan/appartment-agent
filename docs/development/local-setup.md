# Local Setup

Set up a local development environment for AppArt Agent.

## Option 1: Docker (Recommended)

Docker provides the easiest setup with all services configured.

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

```bash
# Clone repository
git clone https://github.com/benjamin-karaoglan/appart-agent.git
cd appart-agent

# Configure environment
cp .env.example .env
# Add your GOOGLE_CLOUD_API_KEY

# Start services
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head
```

### Services

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |

## Option 2: Local Development

Run services directly on your machine for faster iteration.

### Prerequisites

Install required tools:

```bash
# Python (macOS)
brew install python@3.11

# UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js (macOS)
brew install node@20

# pnpm
npm install -g pnpm

# PostgreSQL
brew install postgresql@15
brew services start postgresql@15

# Redis
brew install redis
brew services start redis
```

### Backend Setup

```bash
cd backend

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with local database URL:
# DATABASE_URL=postgresql://localhost:5432/appart_agent

# Create database
createdb appart_agent

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Configure environment
cp .env.local.example .env.local
# Edit: NEXT_PUBLIC_API_URL=http://localhost:8000

# Start development server
pnpm dev
```

### MinIO Setup (Optional)

For document upload testing with local storage:

```bash
# Install MinIO
brew install minio/stable/minio

# Start MinIO
minio server ~/minio-data --console-address ":9001"

# Configure bucket (in another terminal)
brew install minio/stable/mc
mc alias set local http://localhost:9000 minioadmin minioadmin
mc mb local/documents
```

### Google Cloud Storage with Service Account Impersonation (Recommended)

For local development with real GCS buckets (matching production), use service account impersonation. This ensures you have the same permissions as the deployed application.

#### Step 1: Grant Impersonation Permission

First, grant your Google account permission to impersonate the backend service account:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  appart-backend@appart-agent-prod.iam.gserviceaccount.com \
  --member="user:YOUR_EMAIL@gmail.com" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=appart-agent-prod
```

#### Step 2: Login with Impersonation

Generate Application Default Credentials (ADC) that impersonate the service account:

```bash
gcloud auth application-default login \
  --impersonate-service-account=appart-backend@appart-agent-prod.iam.gserviceaccount.com
```

This creates credentials at `~/.config/gcloud/application_default_credentials.json`.

#### Step 3: Start with GCS Backend

```bash
# Using the dev script
./dev.sh start-gcs

# Or manually with docker-compose
docker-compose -f docker-compose.yml -f docker-compose.gcs.yml up -d
```

The `docker-compose.gcs.yml` automatically mounts your ADC credentials into the container.

#### Step 4: Configure GCS Buckets

In your `.env` file:

```bash
STORAGE_BACKEND=gcs
GCS_DOCUMENTS_BUCKET=your-project-documents
GCS_PHOTOS_BUCKET=your-project-photos
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=europe-west1
GEMINI_USE_VERTEXAI=true
```

!!! tip "Benefits of Service Account Impersonation"
    - **Consistent permissions**: Test with the exact same permissions as production
    - **No key management**: No need to download or rotate service account keys
    - **Audit trail**: All actions are logged under your identity, impersonating the service account
    - **Easy revocation**: Remove impersonation access without affecting the service account

## IDE Setup

### VS Code

Recommended extensions:

- Python (Microsoft)
- Pylance
- ESLint
- Tailwind CSS IntelliSense
- Docker
- GitLens

Settings (`.vscode/settings.json`):

```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": "explicit"
  },
  "python.defaultInterpreterPath": "./backend/.venv/bin/python",
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  },
  "files.autoSave": "afterDelay",
  "files.autoSaveDelay": 1000,
  "typescript.preferences.importModuleSpecifier": "relative"
}
```

### PyCharm

1. Open `backend/` as project
2. Configure interpreter: `.venv/bin/python`
3. Mark `app/` as Sources Root
4. Enable FastAPI support

## Database Management

### Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Add new field"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Show current version
alembic current
```

### Direct Access

```bash
# Connect to database
psql appart_agent

# Or with Docker
docker-compose exec db psql -U appart -d appart_agent
```

## Environment Variables

### Backend (.env)

```bash
# Database
DATABASE_URL=postgresql://localhost:5432/appart_agent

# AI
GOOGLE_CLOUD_API_KEY=your_api_key
GEMINI_LLM_MODEL=gemini-2.0-flash-lite

# Security
SECRET_KEY=dev-secret-key-change-in-production

# Storage (local MinIO)
STORAGE_BACKEND=minio
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Logging
LOG_LEVEL=DEBUG
```

### Frontend (.env.local)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Troubleshooting

### Python Import Errors

```bash
# Verify virtual environment is active
which python  # Should show .venv/bin/python

# Reinstall dependencies
uv pip install -e ".[dev]"
```

### Database Connection Failed

```bash
# Check PostgreSQL is running
pg_isready

# Verify database exists
psql -l | grep appart_agent
```

### Port Already in Use

```bash
# Find process
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Node Module Issues

```bash
# Clear cache and reinstall
rm -rf node_modules .next
pnpm install
```
