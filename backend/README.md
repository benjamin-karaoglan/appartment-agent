# Appartment Agent Backend

AI-powered apartment purchasing decision platform for France - Backend API

## Features

- **Multimodal Document Parsing**: Uses Claude's vision capabilities to parse PDF documents (diagnostics, PV d'AG, tax documents)
- **Comprehensive Logging**: Full logging support with file rotation and error tracking
- **Fast Dependency Management**: Uses `uv` for lightning-fast package installation
- **RESTful API**: FastAPI-based backend with automatic OpenAPI documentation

## Quick Start

### Using Docker (Recommended)

```bash
# From the root directory
docker-compose up
```

### Local Development with uv

1. Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create a virtual environment and install dependencies:
```bash
cd backend
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the application:
```bash
uvicorn app.main:app --reload
```

### Local Development with pip

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Configuration

Key environment variables (set in `.env`):

- `DATABASE_URL`: PostgreSQL connection string
- `ANTHROPIC_API_KEY`: Your Anthropic API key for Claude
- `SECRET_KEY`: Secret key for JWT token generation
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## Logging

Logs are stored in the `logs/` directory:
- `app.log`: All application logs with rotation (10MB max, 5 backups)
- `errors.log`: Error-level logs only

## Document Processing

The backend now uses Claude's multimodal capabilities to process documents:

1. **Upload**: Documents are uploaded via `/api/documents/upload`
2. **PDF to Images**: PDFs are converted to high-quality images
3. **Multimodal Analysis**: Images are sent to Claude for analysis
4. **Structured Extraction**: Results are parsed and stored in the database

Supported document types:
- **PV d'AG**: Assembly meeting minutes
- **Diagnostics**: DPE, amiante, plomb, termite, electric, gas
- **Tax documents**: Taxe foncière
- **Charges**: Condominium charges

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## DVF Data Management

### Current Database

The database contains **5.4 million DVF property records** across 4 years (2022-2025 Q1-Q2).

### Importing DVF Data

```bash
# Import a specific year (using Docker)
docker-compose exec backend python scripts/import_dvf_chunked.py \
  data/dvf/ValeursFoncieres-2024.txt --year 2024

# Import with custom chunk size for memory-constrained environments
docker-compose exec backend python scripts/import_dvf_chunked.py \
  data/dvf/ValeursFoncieres-2023.txt --year 2023 --read-chunk-size 30000

# Force re-import (bypasses file hash check)
docker-compose exec backend python scripts/import_dvf_chunked.py \
  data/dvf/ValeursFoncieres-2024.txt --year 2024 --force
```

### Migration Management

Database migrations are managed with Alembic:

```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Create a new migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Check current migration version
docker-compose exec backend alembic current

# Rollback one migration
docker-compose exec backend alembic downgrade -1
```

### Import Management

```bash
# View import history
docker-compose exec backend python scripts/rollback_dvf_import.py --list

# Rollback a specific import
docker-compose exec backend python scripts/rollback_dvf_import.py <batch_id>

# Check database status
docker-compose exec db psql -U appartment -d appartment_agent -c \
  "SELECT data_year, COUNT(*) as records FROM dvf_records GROUP BY data_year ORDER BY data_year;"
```

## Testing

```bash
# With uv
uv pip install pytest pytest-asyncio
pytest

# With pip
pip install pytest pytest-asyncio
pytest

# Run DVF service tests specifically
pytest tests/test_dvf_service.py -v
```
