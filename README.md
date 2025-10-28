# Appartment Agent 🏠

An AI-powered platform to help clients make informed decisions when purchasing apartments in France.

## Features

### 🏘️ Price Analysis
- Address-based property search
- DVF (Demandes de Valeurs Foncières) data integration
- Comparable sales analysis
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
- Anthropic Claude API for AI features

### Infrastructure
- Docker & Docker Compose
- Nginx for reverse proxy
- Redis for caching

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

### Running with Docker

```bash
docker-compose up -d
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

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

The application uses France's open DVF (Demandes de Valeurs Foncières) data. You can:
1. Download data from [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/)
2. Place CSV files in the `data/dvf/` directory
3. Run the import script: `python backend/scripts/import_dvf.py`

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
