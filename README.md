# Appartment Agent 🏠

An AI-powered platform to help clients make informed decisions when purchasing apartments in France.

## Recent Updates ✨

- **Fixed Trend Analysis**: Correctly handles grouped multi-unit sales, consistent outlier filtering across all endpoints
- **Market Trend Visualization**: Interactive 5-year price evolution chart with year-over-year changes
- **Analysis Tooltips**: Informative guides explaining Simple vs Trend analysis methodologies
- **Multimodal Document Parsing**: Uses Claude's vision API to analyze PDFs as images, preserving tables, diagrams, and visual layout
- **Comprehensive Logging**: Full Python logging infrastructure for debugging with rotating log files
- **Optimized Docker Builds**: Multi-stage builds with layer caching for 10-20x faster rebuilds
- **UV Package Manager**: Faster dependency resolution and installation
- **Enhanced Diagnostics**: Better error tracking and debugging capabilities

## Features

### 🏘️ Price Analysis
- **Address-based property search** with DVF (Demandes de Valeurs Foncières) data integration
- **Simple Analysis**: Shows historical sales at exact address with grouped multi-unit transactions
- **Trend Analysis**: Projects 2025 value using neighboring sales trends (2024-2025 data)
- **Market Evolution Chart**: Interactive 5-year price visualization with YoY changes
- **Outlier Detection**: IQR-based filtering for accurate price calculations
- **Interactive Tooltips**: Explains analysis methodologies and when to use each
- Price recommendation and bargaining insights

### 📄 Document Analysis
- **PV d'AG Analysis**: Upload past 3 years of assembly meeting minutes to identify upcoming costs and copropriété works
- **Diagnostic Analysis**: Automated review of DPE, plomb, and amiante reports with risk flagging
- **Tax & Charges Parser**: Extract and annualize costs from Taxe Foncière and charges documents

### 🎨 AI-Powered Visualization
- Upload apartment photos
- AI-driven style transformation based on your preferences
- Visualize renovation potential

### 📊 Decision Dashboard
- Comprehensive cost breakdown
- Investment analysis
- Risk assessment score
- Comparative market analysis
- PDF report generation

## Technology Stack

### Frontend
- Next.js 14 (React 18)
- TypeScript
- Tailwind CSS
- Shadcn/ui components
- React Query for data fetching

### Backend
- FastAPI (Python 3.11+)
- SQLAlchemy ORM
- PostgreSQL database
- Pydantic for validation
- Anthropic Claude API with **multimodal vision** for document parsing
- PyMuPDF for PDF-to-image conversion
- Comprehensive Python logging infrastructure

### Infrastructure
- Docker & Docker Compose with optimized multi-stage builds
- UV for fast Python dependency management
- Nginx for reverse proxy (planned)
- Redis for caching (planned)

## Project Structure

```
appartment-agent/
├── frontend/              # Next.js application
│   ├── src/
│   │   ├── app/          # App router pages
│   │   ├── components/   # React components
│   │   ├── lib/          # Utilities and helpers
│   │   └── types/        # TypeScript types
│   └── public/           # Static assets
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── api/          # API routes
│   │   ├── core/         # Core functionality
│   │   ├── models/       # Database models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── main.py       # Application entry
│   └── requirements.txt
├── data/                 # DVF data storage
├── uploads/              # User uploaded files
├── docs/                 # Documentation
└── docker-compose.yml    # Docker configuration
```

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)
- Anthropic API key

### Environment Variables

Create `.env` files in both frontend and backend directories:

**Backend `.env`:**
```
DATABASE_URL=postgresql://user:password@db:5432/appartment_agent
ANTHROPIC_API_KEY=your_api_key_here
SECRET_KEY=your_secret_key_here
ENVIRONMENT=development
```

**Frontend `.env.local`:**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Running with Docker (Hot-Reload Enabled)

#### Quick Start
```bash
# Using the dev helper script (recommended)
./dev.sh start

# Or directly with docker-compose
docker-compose up
```

**Services:**
- Frontend: http://localhost:3000 (Next.js Fast Refresh)
- Backend API: http://localhost:8000 (Uvicorn --reload)
- API Docs: http://localhost:8000/docs

**Hot-Reload is Active!** Edit any file and watch it reload automatically:
- **Backend (.py files)**: ~1 second restart
- **Frontend (.tsx/.ts files)**: Instant browser update

#### Dev Script Commands
```bash
./dev.sh start      # Start all services
./dev.sh logs       # View all logs
./dev.sh logs backend  # View backend logs only
./dev.sh restart backend  # Restart backend
./dev.sh stop       # Stop all services
./dev.sh help       # See all commands
```

See [HOT_RELOAD_GUIDE.md](HOT_RELOAD_GUIDE.md) for detailed information.

### Local Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Key Features Roadmap

- [x] Project structure and architecture
- [ ] User authentication and authorization
- [ ] Address search and DVF integration
- [ ] Price analysis and recommendations
- [ ] PV d'AG document upload and AI analysis
- [ ] Diagnostic document analysis (DPE, plomb, amiante)
- [ ] Tax and charges parser
- [ ] Photo upload and AI style transformation
- [ ] Decision dashboard and scoring
- [ ] PDF report generation
- [ ] Multi-property comparison
- [ ] Email notifications
- [ ] Mobile responsive design

## DVF Data Integration

The application uses France's open DVF (Demandes de Valeurs Foncières) data for price analysis.

### Current Database Status

The database contains **5.4 million property records** across 4 years:
- **2022**: 1,933,436 sales
- **2023**: 1,518,590 sales
- **2024**: 1,367,286 sales
- **2025 (Q1-Q2)**: 567,471 sales

### Production-Ready Import System

The DVF import system features:
- **UPSERT Logic**: Safe, idempotent imports that prevent duplicates
- **File Hash Checking**: Prevents re-importing the same file
- **Batch Processing**: Memory-efficient chunked processing for large files (400MB-600MB)
- **Transaction Safety**: Rollback on errors with complete audit trail
- **Versioning**: Track exactly which DVF files and years are imported
- **Deduplication**: Unique constraint on (sale_date, sale_price, address, postal_code, surface_area)

### How to Import DVF Data

1. **Download Latest Data**:
   - Visit [data.gouv.fr DVF datasets](https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/)
   - Download the latest yearly files (e.g., ValeursFoncieres-2024.txt)
   - File format: Pipe-delimited CSV (|)
   - Save to `data/dvf/` directory

2. **Import Using Docker** (Recommended):
   ```bash
   # Import a specific year using the chunked importer
   docker-compose exec backend python scripts/import_dvf_chunked.py \
     data/dvf/ValeursFoncieres-2024.txt --year 2024

   # Import with custom chunk sizes for memory-constrained environments
   docker-compose exec backend python scripts/import_dvf_chunked.py \
     data/dvf/ValeursFoncieres-2023.txt --year 2023 --read-chunk-size 30000

   # Force re-import (bypasses file hash check)
   docker-compose exec backend python scripts/import_dvf_chunked.py \
     data/dvf/ValeursFoncieres-2024.txt --year 2024 --force
   ```

3. **View Import History**:
   ```bash
   # Check import status and statistics
   docker-compose exec db psql -U appartment -d appartment_agent -c \
     "SELECT source_file, data_year, status, total_records, inserted_records,
      duration_seconds, started_at FROM dvf_imports ORDER BY started_at DESC;"

   # Check data by year
   docker-compose exec db psql -U appartment -d appartment_agent -c \
     "SELECT data_year, COUNT(*) as records, MIN(sale_date), MAX(sale_date)
      FROM dvf_records GROUP BY data_year ORDER BY data_year;"
   ```

4. **Rollback an Import** (if needed):
   ```bash
   # List all imports to find batch_id
   docker-compose exec backend python scripts/rollback_dvf_import.py --list

   # Rollback a specific import
   docker-compose exec backend python scripts/rollback_dvf_import.py <batch_id>
   ```

### Import Process Details

The chunked importer:
- Reads CSV files in chunks (default 30,000 rows) to minimize memory usage
- Cleans and validates data (postal codes, street numbers, sale prices, dates)
- Filters for apartments, houses, and Dépendance (storage units)
- Handles multi-property transactions correctly
- Deduplicates both within batches and across imports using PostgreSQL UPSERT
- Calculates price per m² automatically
- Creates full audit trail in `dvf_imports` table

**Performance**: Processes ~1,000 records/sec with chunked reading, completing a 600MB file in ~5 minutes.

### Database Schema Enhancements

The production system includes:
- **GIN indexes** for fast address search (using pg_trgm extension)
- **Composite indexes** for common query patterns (postal_code + property_type + address)
- **Partial indexes** for conditional queries (price_per_sqm > 0)
- **Unique constraints** to guarantee no duplicate sales
- **Import tracking** table for complete audit trail

### Verification

Check total records and data coverage:
```bash
# Total DVF records
docker-compose exec db psql -U appartment -d appartment_agent -c \
  "SELECT COUNT(*) as total_records FROM dvf_records;"

# Records by year
docker-compose exec db psql -U appartment -d appartment_agent -c \
  "SELECT data_year, COUNT(*) as records FROM dvf_records
   GROUP BY data_year ORDER BY data_year;"
```

### Example: Missing Sales

**Scenario**: You search for "56 RUE NOTRE-DAME DES CHAMPS 75006" and the app shows only 1 sale (2024), but the official DVF website shows:
- 1,268,540 € - 08/11/2024
- 614,400 € - 24/10/2024
- 1,325,200 € - 13/02/2023

**Reason**: Your imported DVF dataset is missing recent sales. Download and import the latest 2024 DVF data to see all sales.

### Testing Your Data

After importing, verify data completeness:

```bash
cd backend
source venv/bin/activate

# Test specific address
python -c "
from app.core.database import SessionLocal
from app.models.property import DVFRecord
db = SessionLocal()
records = db.query(DVFRecord).filter(DVFRecord.address.like('56 RUE NOTRE-DAME DES CHAMPS%')).all()
print(f'Found {len(records)} sales for 56 RUE NOTRE-DAME DES CHAMPS')
for r in records:
    print(f'  - {r.sale_date}: {r.sale_price:,.0f} EUR')
db.close()
"
```

### Unit Tests

The DVF service includes comprehensive unit tests to ensure data accuracy:

```bash
cd backend
source venv/bin/activate
pytest tests/test_dvf_service.py -v
```

Tests cover:
- Address parsing and extraction
- Price trend calculation
- Time-based price adjustments
- Market analysis and recommendations
- Date/datetime handling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License

## Support

For issues and questions, please open a GitHub issue.

---

**Note**: This application is designed for the French real estate market and uses France-specific data sources and regulations.
