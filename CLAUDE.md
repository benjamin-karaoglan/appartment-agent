# CLAUDE.md

## Project Overview

**AppArt Agent** is an AI-powered apartment purchasing decision platform for the French real estate market. It's a monorepo with a FastAPI backend, Next.js frontend, and GCP-based infrastructure.

## Architecture

```text
/
├── backend/          # FastAPI API (Python 3.10)
├── frontend/         # Next.js 14 app (React 18, TypeScript)
├── infra/            # Terraform IaC for GCP
├── docs/             # MkDocs documentation site
├── scripts/          # GCP bootstrap scripts
├── data/             # DVF dataset (5M+ French property transactions)
└── docker-compose.yml
```

### Backend (`backend/`)

- **Framework**: FastAPI with Uvicorn (ASGI)
- **ORM**: SQLAlchemy 2.0 with Alembic migrations
- **AI**: Google Gemini (gemini-2.5-flash for text, gemini-2.5-flash-image for images) via `google-genai` SDK. Supports Vertex AI (production) or REST API key (development).
- **Auth**: Better Auth (session-based, managed by frontend) with legacy JWT fallback
- **Storage**: MinIO (local dev) / Google Cloud Storage (production) -- abstracted in `app/services/storage.py`
- **Entry point**: `backend/app/main.py`
- **Config**: `backend/app/core/config.py` (Pydantic settings from env vars)
- **API routes**: `backend/app/api/` (users, properties, documents, photos, analysis, webhooks)
- **Services**: `backend/app/services/` (ai/, documents/, storage, dvf_service, price_analysis)
- **Models**: `backend/app/models/` (user, property, document, photo, analysis, dvf)

### Frontend (`frontend/`)

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript 5.3
- **Styling**: Tailwind CSS 3.3 with semantic design tokens
- **UI Components**: Shared component library (`frontend/src/components/ui/`)
- **State**: TanStack React Query v5
- **Auth**: Better Auth 1.4 with Google OAuth support
- **i18n**: next-intl (locales: `fr`, `en`, default: `fr`)
- **Icons**: Lucide React
- **PWA**: `@ducanh2912/next-pwa` (installable on mobile, disabled in dev)
- **API client**: Axios (`frontend/src/lib/api.ts`) hitting `NEXT_PUBLIC_API_URL`
- **Pages**: `frontend/src/app/[locale]/` (dashboard, properties, documents, photos, redesign-studio)
- **Package manager**: pnpm

#### Design System

The frontend uses a semantic color token system defined in `tailwind.config.js`. **Never use raw Tailwind color names** (e.g., `blue-600`, `red-500`). Always use the semantic tokens:

| Token | Palette | Usage |
|-------|---------|-------|
| `primary-*` | Blue (#2563eb) | Main CTAs, links, active states, focus rings |
| `accent-*` | Indigo (#4f46e5) | Secondary features: studio, photos, documents, AI |
| `success-*` | Emerald (#10b981) | Positive states, confirmations |
| `warning-*` | Amber (#f59e0b) | Warnings, outliers, caution states |
| `danger-*` | Red (#dc2626) | Errors, destructive actions, high risk |

Shared UI components live in `frontend/src/components/ui/`:

| Component | Purpose |
|-----------|---------|
| `Button` | 6 variants (primary, secondary, accent, ghost, danger, link), 2 sizes |
| `Badge` | 6 variants (success, warning, danger, info, accent, neutral) |
| `Card` | Consistent card wrapper with padding options |
| `SectionHeader` | Section title with icon and optional action |
| `StatCard` | Dashboard stat card with icon |

Utility CSS classes are defined in `globals.css` (`btn-primary`, `btn-secondary`, `badge-success`, etc.).

#### PWA (Progressive Web App)

The app is installable on mobile devices via `@ducanh2912/next-pwa`. Configuration is in `next.config.js`:

- **Disabled in development** (`disable: process.env.NODE_ENV === 'development'`)
- Service worker and Workbox files (`sw.js`, `workbox-*.js`) are generated during `pnpm build` into `public/` and gitignored
- Manifest at `frontend/public/manifest.json`, icons in `frontend/public/icons/`
- PWA metadata (viewport, manifest link, apple-web-app) in `frontend/src/app/[locale]/layout.tsx`
- Stale service workers are auto-unregistered in development via `Providers.tsx`

**Important**: Never commit generated `sw.js` or `workbox-*.js` files. They are build artifacts.

## Development Setup

### Prerequisites

- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+ with pnpm 10+
- Copy `.env.example` to `.env` and fill in required values

### Running the Dev Environment

Everything runs via Docker Compose. Use the helper script:

```bash
./dev.sh start          # Start all services (MinIO storage)
./dev.sh start-gcs      # Start with Google Cloud Storage instead
./dev.sh stop           # Stop all services
./dev.sh logs [service] # Follow logs (backend, frontend, db, redis, minio)
./dev.sh restart <svc>  # Restart a specific service
./dev.sh rebuild [svc]  # Rebuild and restart
./dev.sh status         # Show service status
./dev.sh shell [svc]    # Shell into container (default: backend)
```

### Services (docker-compose)

| Service    | URL                        | Notes                          |
|------------|----------------------------|--------------------------------|
| Backend    | http://localhost:8000      | API docs at /docs              |
| Frontend   | http://localhost:3000      | Next.js with HMR              |
| PostgreSQL | localhost:5432             | postgres:15-alpine             |
| Redis      | localhost:6379             | redis:7-alpine                 |
| MinIO      | http://localhost:9000      | Console at http://localhost:9001 |

Database migrations run automatically via the `migrations` service on `docker-compose up`.

**Storage backend**: `docker-compose.yml` defaults to MinIO (`STORAGE_BACKEND=minio`) but respects the `.env` override. If `.env` has `STORAGE_BACKEND=gcs`, the backend uses Google Cloud Storage. After switching backends, flush the Redis presigned URL cache: `docker compose exec redis redis-cli EVAL "local k=redis.call('KEYS','presigned_url:*'); if #k>0 then return redis.call('DEL',unpack(k)) else return 0 end" 0`

### Running Tests

Tests run on the host using uv:

```bash
cd backend
uv run pytest                    # Run all tests
uv run pytest --cov              # With coverage
uv run pytest tests/test_dvf_service.py  # Specific test file
```

Testing stack: pytest + pytest-asyncio + pytest-cov.

## Dependency Management

### Python (uv only -- never use pip)

```bash
uv add <package>        # Add a dependency
uv remove <package>     # Remove a dependency
uv sync                 # Sync from lock file
uv run <command>        # Run a command in the venv
```

Lock file: `uv.lock` (root level). Backend deps defined in `backend/pyproject.toml`.

### Frontend (pnpm)

```bash
cd frontend
pnpm install            # Install deps
pnpm dev                # Dev server (but prefer docker-compose)
pnpm build              # Production build
pnpm lint               # ESLint
```

Lock file: `frontend/pnpm-lock.yaml`.

## Code Quality & Linting

### Pre-commit Hooks

Pre-commit is configured (`.pre-commit-config.yaml`) and runs automatically on commit:

- **Python**: ruff (lint + format), mypy (type check), bandit (security)
- **Frontend**: ESLint, TypeScript type check (`tsc --noEmit`)
- **Markdown**: markdownlint-cli2
- **General**: trailing whitespace, EOF fixer, YAML/JSON/TOML checks, large file detection
- **Secrets**: gitleaks
- **Commits**: conventional-pre-commit (enforces conventional commit format)

### Manual Linting

```bash
uv run ruff check backend/     # Python lint
uv run ruff format backend/    # Python format
cd frontend && pnpm lint       # Frontend lint
pre-commit run --all-files     # Run all hooks
```

### Ruff Config

- Line length: 100
- Target: Python 3.10
- Ignores: E501 (line length), E711/E712 (SQLAlchemy comparison patterns)

## Git Conventions

### Commits

**Conventional commits are enforced by pre-commit.** Allowed types:

`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

Examples:

```text
feat: add tantieme detection to document analysis
fix: bulk upload status lost on page reload
docs: update DVF import guide
```

### Branching

- `main` -- production, deployed to GCP Cloud Run
- `develop` -- integration branch, PR target for features
- Never push directly to `main`

### Pull Requests

- Target `develop` for feature work
- Target `main` only for releases/hotfixes

## Environment Variables

Key variables (see `.env.example` for full list):

| Variable | Purpose |
|----------|---------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | GCP region (default: us-central1) |
| `GEMINI_USE_VERTEXAI` | Use Vertex AI (production) vs REST API key (dev) |
| `GOOGLE_CLOUD_API_KEY` | Gemini REST API key (only needed when `GEMINI_USE_VERTEXAI=false`) |
| `GEMINI_LLM_MODEL` | Text analysis model (default: gemini-2.5-flash) |
| `GEMINI_IMAGE_MODEL` | Image generation model (default: gemini-2.5-flash-image) |
| `BETTER_AUTH_SECRET` | Auth secret (32+ chars) |
| `SECRET_KEY` | Backend secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `STORAGE_BACKEND` | `minio` (dev) or `gcs` (prod) |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO credentials |
| `GCS_DOCUMENTS_BUCKET` / `GCS_PHOTOS_BUCKET` | GCS bucket names |
| `LOGFIRE_TOKEN` | Observability (optional) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth (optional) |

**Never commit `.env` files.** They are in `.gitignore`.

## Infrastructure & Deployment

### GCP Architecture (Production)

- **Compute**: Google Cloud Run (serverless containers)
- **Database**: Cloud SQL (PostgreSQL)
- **Storage**: Google Cloud Storage (documents + photos buckets)
- **AI**: Vertex AI (managed Gemini models)
- **Registry**: Google Artifact Registry (Docker images)
- **IaC**: Terraform (`infra/terraform/`)

### Terraform

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

Managed resources: Cloud Run services, GCS buckets, IAM, Vertex AI config.

### GCP Bootstrap

First-time GCP setup:

```bash
./scripts/gcp-bootstrap.sh  # Enables APIs, creates resources, sets up Terraform
```

### Docker Images

- **Backend**: Multi-stage build (`backend/Dockerfile`) -- builder, dev, production stages. Uses uv for fast installs. Production runs as non-root `appuser`.
- **Frontend**: `frontend/Dockerfile.pnpm` for production (pnpm-optimized). `frontend/Dockerfile` for dev.

### CI/CD (GitHub Actions)

`.github/workflows/deploy.yml`:

1. **Build & Test**: Python (uv + ruff + pytest), Node.js (pnpm + eslint + tsc)
2. **Push images**: To Artifact Registry (on main branch only)
3. **Migrate DB**: Run Alembic migrations
4. **Deploy**: Backend + Frontend to Cloud Run

`.github/workflows/docs.yml`: Builds and deploys MkDocs to GitHub Pages.

## Key Domain Concepts

- **DVF** (Demandes de Valeurs Foncieres): French government open dataset of 5M+ property transactions (2022-2025). Used for price analysis and market comparisons.
- **PV AG** (Proces-Verbal d'Assemblee Generale): Minutes from co-ownership meetings -- analyzed for risk flags, pending works, copropriete health.
- **Diagnostics**: Building diagnostics (amiante, plomb, DPE/GES energy ratings).
- **Redesign Studio**: AI-powered apartment photo transformation using Gemini image generation with style presets (modern_norwegian, minimalist_scandinavian, cozy_hygge).
- **Synthesis**: Cross-document aggregated analysis per property with cost breakdowns and risk assessments.
