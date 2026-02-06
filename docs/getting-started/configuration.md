# Configuration

AppArt Agent uses environment variables for configuration. This guide covers all available settings.

## Environment Files

| File | Purpose |
|------|---------|
| `.env` | Root-level shared variables |
| `backend/.env` | Backend-specific configuration |
| `frontend/.env.local` | Frontend-specific configuration |

## Root Configuration (.env)

```bash
# AI Provider - Google Cloud (Recommended)
GOOGLE_CLOUD_API_KEY=your_google_api_key
GOOGLE_CLOUD_PROJECT=your_gcp_project         # For Vertex AI
GOOGLE_CLOUD_LOCATION=us-central1             # GCP region
GEMINI_USE_VERTEXAI=false                     # Use Vertex AI instead of API key

# AI Provider - Anthropic (Legacy)
ANTHROPIC_API_KEY=your_anthropic_key          # Optional

# Security
SECRET_KEY=your-secret-key-at-least-32-chars  # Required

# Optional: DVF auto-import on startup
AUTO_IMPORT_DVF=false
```

## Backend Configuration (backend/.env)

### Core Settings

```bash
# Application
ENVIRONMENT=development                        # development | production
LOG_LEVEL=INFO                                 # DEBUG | INFO | WARNING | ERROR

# Database
DATABASE_URL=postgresql://appart:appart@db:5432/appart_agent

# Security
SECRET_KEY=your-secret-key-at-least-32-chars
```

### AI Configuration

```bash
# Gemini Models
GEMINI_LLM_MODEL=gemini-2.0-flash-lite        # Text/document analysis
GEMINI_IMAGE_MODEL=gemini-2.0-flash-exp       # Image generation
GEMINI_USE_VERTEXAI=false                     # true for production on GCP

# Google Cloud (required for Vertex AI)
GOOGLE_CLOUD_API_KEY=your_api_key
GOOGLE_CLOUD_PROJECT=your_project
GOOGLE_CLOUD_LOCATION=us-central1
```

### Storage Configuration

```bash
# Storage Backend: 'minio' (local) or 'gcs' (production)
STORAGE_BACKEND=minio

# MinIO (Local Development)
MINIO_ENDPOINT=minio:9000
MINIO_PUBLIC_ENDPOINT=localhost:9000          # For presigned URLs
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents
MINIO_SECURE=false

# Google Cloud Storage (Production)
GCS_DOCUMENTS_BUCKET=your-documents-bucket
GCS_PHOTOS_BUCKET=your-photos-bucket
```

### Cache Configuration

```bash
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
CACHE_TTL=3600                                # Cache TTL in seconds
```

### File Upload Settings

```bash
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_SIZE=10485760                      # 10MB in bytes
```

## Frontend Configuration (frontend/.env.local)

```bash
# API endpoint
NEXT_PUBLIC_API_URL=http://localhost:8000

# App URL (required for Better Auth callbacks)
NEXT_PUBLIC_APP_URL=http://localhost:3000

# Database (Better Auth needs direct DB access for session management)
DATABASE_URL=postgresql://appart:appart@localhost:5432/appart_agent

# Better Auth secret (generate with: openssl rand -hex 32)
BETTER_AUTH_SECRET=your-better-auth-secret-at-least-32-characters

# Google OAuth (optional - leave empty to disable)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

### Better Auth Setup

Authentication is handled by [Better Auth](https://www.better-auth.com/) via Next.js API routes. The backend validates sessions by checking the `better-auth.session_token` cookie against the `ba_session` database table.

**Required variables:**

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_APP_URL` | Yes | Frontend URL (for OAuth callbacks) |
| `DATABASE_URL` | Yes | PostgreSQL connection (Better Auth session storage) |
| `BETTER_AUTH_SECRET` | Yes | Secret for signing session cookies (32+ chars) |
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID (enables Google sign-in) |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth client secret |

**Generate a secret:**

```bash
openssl rand -hex 32
```

**Google OAuth setup (optional):**

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create an OAuth 2.0 Client ID (Web application)
3. Add redirect URIs:
   - Local: `http://localhost:3000/api/auth/callback/google`
   - Production: `https://your-frontend-url/api/auth/callback/google`
4. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`

## Configuration by Environment

### Development

```bash
# .env
ENVIRONMENT=development
LOG_LEVEL=DEBUG
STORAGE_BACKEND=minio
GEMINI_USE_VERTEXAI=false

# Uses local MinIO for storage
# Uses Gemini API key directly
```

### Production (GCP)

```bash
# Set via Secret Manager or Cloud Run env vars
ENVIRONMENT=production
LOG_LEVEL=INFO
STORAGE_BACKEND=gcs
GEMINI_USE_VERTEXAI=true

# Uses Google Cloud Storage
# Uses Vertex AI with service account
```

### Local Development with GCS (Service Account Impersonation)

For testing locally with real GCP services while maintaining production parity:

```bash
# .env
ENVIRONMENT=development
LOG_LEVEL=DEBUG
STORAGE_BACKEND=gcs
GEMINI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=europe-west1
GCS_DOCUMENTS_BUCKET=your-project-documents
GCS_PHOTOS_BUCKET=your-project-photos
```

**Setup impersonation** (one-time):

```bash
# 1. Grant yourself permission to impersonate the backend service account
gcloud iam service-accounts add-iam-policy-binding \
  appart-backend@your-project-id.iam.gserviceaccount.com \
  --member="user:your-email@gmail.com" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=your-project-id

# 2. Login with impersonation
gcloud auth application-default login \
  --impersonate-service-account=appart-backend@your-project-id.iam.gserviceaccount.com

# 3. Start with GCS backend
./dev.sh start-gcs
```

!!! tip "Why use impersonation?"
    - Test with the exact same permissions as production
    - No service account key files to manage or secure
    - Easy to revoke access without affecting the service account
    - All actions logged under your identity for audit purposes

## Security Best Practices

!!! danger "Never commit secrets"
    - Add `.env` files to `.gitignore`
    - Use environment variables or secret managers in production
    - Rotate API keys regularly

### Generating a Secret Key

```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### API Key Security

1. **Restrict API key permissions** in Google Cloud Console
2. **Set quotas** to prevent unexpected charges
3. **Monitor usage** via Cloud Console

## CORS Configuration

For custom domains, add to backend config:

```bash
# Comma-separated list of additional origins
EXTRA_CORS_ORIGINS=https://app.yourdomain.com,https://staging.yourdomain.com
```

## Validation

Verify configuration is correct:

```bash
# Check backend config
docker-compose exec backend python -c "
from app.core.config import settings
print(f'Environment: {settings.ENVIRONMENT}')
print(f'Database: {settings.DATABASE_URL[:30]}...')
print(f'Storage: {settings.STORAGE_BACKEND}')
print(f'AI Model: {settings.GEMINI_LLM_MODEL}')
"
```

## Configuration Reference

### Backend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `SECRET_KEY` | Yes | - | Legacy auth signing key (32+ chars) |
| `GOOGLE_CLOUD_API_KEY` | Yes* | - | Gemini API key |
| `STORAGE_BACKEND` | No | `minio` | Storage: `minio` or `gcs` |
| `GEMINI_LLM_MODEL` | No | `gemini-2.0-flash-lite` | Text analysis model |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `REDIS_HOST` | No | `redis` | Redis hostname |
| `CACHE_TTL` | No | `3600` | Cache TTL in seconds |

*Required unless using Vertex AI with service account

### Frontend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | - | Backend API URL |
| `NEXT_PUBLIC_APP_URL` | Yes | - | Frontend URL (for auth callbacks) |
| `DATABASE_URL` | Yes | - | PostgreSQL connection (Better Auth) |
| `BETTER_AUTH_SECRET` | Yes | - | Session cookie signing secret (32+ chars) |
| `GOOGLE_CLIENT_ID` | No | - | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | No | - | Google OAuth client secret |
