# AppArt Agent

**AI-powered apartment purchasing decision platform for France**

AppArt Agent helps buyers make informed real estate decisions by combining French property transaction data (DVF) with AI-powered document analysis and visualization tools.

## Features at a Glance

```mermaid
flowchart LR
    subgraph Input["Your Input"]
        Address["Property Address"]
        Docs["Documents<br/>(PV AG, Diagnostics,<br/>Tax, Charges, Other)"]
        Photos["Apartment Photos"]
    end

    subgraph AI["AI Analysis"]
        DVF["Price Analysis<br/>5.4M+ transactions"]
        DocAI["Document Analysis<br/>Native PDF + Thinking"]
        PhotoAI["Photo Redesign<br/>Style visualization"]
    end

    subgraph Output["Decision Support"]
        Price["Market Valuation"]
        Risks["Risk Assessment<br/>+ Confidence Score"]
        Costs["Cost Breakdown<br/>+ Tantiemes"]
        Visual["Renovation Preview<br/>+ Promoted Redesigns"]
    end

    Address --> DVF --> Price
    Docs --> DocAI --> Risks
    Docs --> DocAI --> Costs
    Photos --> PhotoAI --> Visual
```

### Price Analysis

Access 5.4M+ French property transactions from DVF data to understand market prices, trends, and get personalized recommendations.

[Learn more →](backend/dvf-data.md)

### Document Analysis

Upload PV d'AG, diagnostics, tax documents, charges, and other property documents (rules, contracts, insurance). AI automatically classifies, analyzes with native PDF processing and reasoning, and produces a cross-document synthesis with cost breakdowns, tantiemes calculation, risk factors, and buyer action items.

[Learn more →](backend/ai-services.md)

### Photo Redesign

Visualize renovation potential with AI-powered style transformation of apartment photos. Promote your favorite redesign to feature it on the property overview.

[Learn more →](backend/ai-services.md#image-generator)

### Decision Dashboard

Property overview with AI synthesis summary, risk level badges, annual/one-time cost breakdowns, promoted redesign previews, and inline property editing.

[Learn more →](frontend/pages.md)

## Quick Start

```bash
# Clone and setup
git clone https://github.com/benjamin-karaoglan/appart-agent.git
cd appart-agent
cp .env.example .env
# Add your GOOGLE_CLOUD_API_KEY to .env

# Start services
docker-compose up -d
docker-compose exec backend alembic upgrade head

# Access
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

[Full installation guide →](getting-started/quickstart.md)

## Architecture Overview

```mermaid
flowchart TB
    subgraph Client["Client Browser"]
        Browser["Web Browser"]
    end

    subgraph Frontend["Frontend - Next.js 14"]
        Dashboard["Dashboard<br/>+ Synthesis Preview"]
        Documents["Documents<br/>+ Multi-phase Processing"]
        Properties["Property Detail<br/>+ Inline Editing"]
        Photos["Photo Studio<br/>+ Promoted Redesigns"]
    end

    subgraph Backend["Backend - FastAPI"]
        API["REST API"]
        AIServices["AI Services<br/>Native PDF + Thinking"]
        DocProcessing["Document Processing<br/>+ Cross-doc Synthesis"]
    end

    subgraph DataLayer["Data Layer"]
        PostgreSQL[("PostgreSQL<br/>5.4M+ DVF")]
        Redis[("Redis Cache")]
        Storage[("MinIO / GCS")]
    end

    subgraph External["External Services"]
        Gemini["Google Gemini<br/>Vertex AI"]
    end

    Browser --> Frontend
    Frontend --> Backend
    API --> PostgreSQL
    AIServices --> Redis
    DocProcessing --> Storage
    AIServices --> Gemini
    Properties --> API
```

[Architecture details →](architecture/overview.md)

## Deployment Options

```mermaid
flowchart LR
    subgraph Local["Local Development"]
        Docker["Docker Compose<br/>Free, all-in-one"]
    end

    subgraph Cloud["Production"]
        GCP["GCP Cloud Run<br/>~$65-445/month"]
    end

    Local -->|"Ready for prod?"| Cloud
```

| Environment | Best For | Guide |
|-------------|----------|-------|
| Docker Compose | Development, testing | [Docker Guide](deployment/docker.md) |
| GCP Cloud Run | Production, scaling | [GCP Guide](deployment/gcp.md) |

## Technology Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS, Better Auth, next-intl, pnpm |
| **Backend** | FastAPI, Python 3.10+, SQLAlchemy, UV |
| **Auth** | Better Auth (email/password + Google OAuth), HTTP-only session cookies |
| **AI/ML** | Google Gemini 2.0, Vertex AI, LangChain |
| **Database** | PostgreSQL 15, Redis 7 |
| **Storage** | MinIO (local), Google Cloud Storage (production) |
| **Infrastructure** | Docker, Terraform, GCP Cloud Run |

## Documentation Sections

```mermaid
flowchart TB
    Start["Getting Started"]
    Arch["Architecture"]
    Backend["Backend"]
    Frontend["Frontend"]
    Deploy["Deployment"]
    Dev["Development"]

    Start --> Arch
    Arch --> Backend
    Arch --> Frontend
    Backend --> Deploy
    Frontend --> Deploy
    Deploy --> Dev
```

- **[Getting Started](getting-started/index.md)** - Installation, prerequisites, and configuration
- **[Architecture](architecture/index.md)** - System design and data flow
- **[Backend](backend/index.md)** - API reference, AI services, database models
- **[Frontend](frontend/index.md)** - Pages, components, and UI patterns
- **[Deployment](deployment/index.md)** - Docker and GCP deployment guides
- **[Development](development/index.md)** - Local setup, testing, and contributing

## Support

- **Issues**: [GitHub Issues](https://github.com/benjamin-karaoglan/appart-agent/issues)
- **License**: [Custom Non-Commercial License](https://github.com/benjamin-karaoglan/appart-agent/blob/main/LICENSE)
