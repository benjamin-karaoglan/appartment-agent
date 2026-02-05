# System Overview

## High-Level Architecture

```mermaid
flowchart TB
    subgraph ClientLayer["Client Layer"]
        Browser["Web Browser<br/>Dashboard | Documents | Photos"]
    end

    subgraph FrontendLayer["Frontend Layer - Next.js 14"]
        subgraph Pages["Pages (App Router)"]
            P1["Dashboard<br/>Investment analysis"]
            P2["Properties<br/>Address search"]
            P3["Documents<br/>Upload & analysis"]
            P4["Photos<br/>AI redesign studio"]
        end

        subgraph Components["Reusable Components"]
            C1["Header / Navigation"]
            C2["Charts (Recharts)"]
            C3["Forms & Inputs"]
            C4["Modals & Tooltips"]
        end

        subgraph APIClient["API Client"]
            AC1["React Query<br/>Data fetching & caching"]
            AC2["TypeScript Types<br/>Type-safe API calls"]
        end
    end

    subgraph BackendLayer["Backend Layer - FastAPI"]
        subgraph Endpoints["API Endpoints"]
            E1["/api/users<br/>Auth & profiles"]
            E2["/api/properties<br/>Property management"]
            E3["/api/documents<br/>Upload & analysis"]
            E4["/api/analysis<br/>Price trends"]
            E5["/api/photos<br/>Redesign generation"]
        end

        subgraph Services["Service Layer"]
            S1["AI Services<br/>Analyzer | Processor | ImageGen"]
            S2["Storage Service<br/>MinIO | GCS abstraction"]
            S3["DVF Service<br/>5.4M+ transactions"]
            S4["Price Analysis<br/>Trends & projections"]
        end
    end

    subgraph DataLayer["Data Layer"]
        PostgreSQL[("PostgreSQL 15<br/>Users | Properties<br/>Documents | DVF")]
        Redis[("Redis 7<br/>Cache | Sessions")]
        Storage[("Object Storage<br/>MinIO / GCS")]
    end

    subgraph ExternalLayer["External Services"]
        Gemini["Google Gemini<br/>Vertex AI"]
    end

    Browser --> FrontendLayer
    FrontendLayer -->|"REST API"| BackendLayer
    Services --> PostgreSQL
    Services --> Redis
    Services --> Storage
    S1 --> Gemini
```

## Component Details

### Frontend Architecture

```mermaid
flowchart LR
    subgraph NextJS["Next.js 14 App"]
        subgraph AppRouter["App Router"]
            Layout["Root Layout"]
            Pages["Page Components"]
        end

        subgraph State["State Management"]
            AuthContext["Auth Context"]
            ReactQuery["React Query Cache"]
        end

        subgraph UI["UI Layer"]
            Tailwind["Tailwind CSS"]
            Components["Component Library"]
        end
    end

    Layout --> Pages
    Pages --> State
    Pages --> UI
```

| Directory | Purpose |
|-----------|---------|
| `src/app/` | App Router pages and layouts |
| `src/components/` | Reusable React components |
| `src/contexts/` | React context providers (Auth) |
| `src/lib/` | Utilities and API client |
| `src/types/` | TypeScript type definitions |

**Key Technologies**:

- **React 18** with Server Components
- **Tailwind CSS** for styling
- **React Query** for data fetching and caching
- **TypeScript** for type safety
- **pnpm** for package management

### Backend Architecture

```mermaid
flowchart TB
    subgraph FastAPI["FastAPI Application"]
        subgraph Core["Core"]
            Config["Configuration"]
            DB["Database Session"]
            Security["Auth & Security"]
        end

        subgraph API["API Layer"]
            Routes["Route Handlers"]
            Schemas["Pydantic Schemas"]
        end

        subgraph ServiceLayer["Services"]
            AI["AI Services"]
            Storage["Storage Service"]
            DVF["DVF Service"]
            Analysis["Price Analysis"]
        end

        subgraph Models["Data Models"]
            ORM["SQLAlchemy Models"]
        end
    end

    Routes --> Schemas
    Routes --> ServiceLayer
    ServiceLayer --> Models
    ServiceLayer --> Core
    Models --> DB
```

| Directory | Purpose |
|-----------|---------|
| `app/api/` | REST API route handlers |
| `app/core/` | Configuration, database, security |
| `app/models/` | SQLAlchemy ORM models |
| `app/schemas/` | Pydantic request/response schemas |
| `app/services/` | Business logic and integrations |
| `app/prompts/` | AI prompt templates (versioned) |

**Key Technologies**:

- **FastAPI** for async HTTP handling
- **SQLAlchemy 2.0** for ORM
- **Pydantic v2** for validation
- **Google Generative AI SDK** for Gemini
- **UV** for fast package management

### Data Layer

```mermaid
flowchart LR
    subgraph PostgreSQL["PostgreSQL 15"]
        Users["users"]
        Properties["properties"]
        Documents["documents"]
        DVF["dvf_records<br/>5.4M+ rows"]
    end

    subgraph Redis["Redis 7"]
        Sessions["Session Store"]
        Cache["Query Cache"]
        RateLimit["Rate Limiting"]
    end

    subgraph ObjectStorage["Object Storage"]
        DocBucket["documents/"]
        PhotoBucket["photos/"]
    end
```

#### PostgreSQL

Stores structured data:

| Table | Records | Purpose |
|-------|---------|---------|
| `users` | ~100s | User accounts and authentication |
| `properties` | ~100s | Properties and their metadata |
| `documents` | ~1000s | Documents and analysis results |
| `dvf_records` | 5.4M+ | French property transactions (2022-2025) |

#### Redis

In-memory caching for:

- Session data (7-day TTL)
- Frequently accessed queries (1-hour TTL)
- Rate limiting counters

#### Object Storage (MinIO / GCS)

File storage for:

- Uploaded documents (PDFs, images)
- Generated images (photo redesigns)
- Presigned URLs for secure browser access

## Service Dependencies

```mermaid
graph TD
    subgraph Application["Application Services"]
        Frontend["Frontend<br/>Next.js"]
        Backend["Backend<br/>FastAPI"]
    end

    subgraph Data["Data Services"]
        PostgreSQL[("PostgreSQL")]
        Redis[("Redis")]
        Storage[("MinIO/GCS")]
    end

    subgraph External["External Services"]
        Gemini["Gemini AI<br/>Vertex AI"]
    end

    Frontend -->|"HTTP/REST"| Backend
    Backend -->|"SQL"| PostgreSQL
    Backend -->|"Cache"| Redis
    Backend -->|"Files"| Storage
    Backend -->|"AI API"| Gemini
```

## Security Architecture

### Authentication Flow

```mermaid
sequenceDiagram
    participant User as User Browser
    participant Frontend as Frontend
    participant Backend as Backend API
    participant DB as PostgreSQL

    User->>Frontend: 1. Enter credentials
    Frontend->>Backend: 2. POST /auth/login
    Backend->>DB: 3. Verify password (bcrypt)
    DB-->>Backend: 4. User record
    Backend->>Backend: 5. Generate JWT (HS256)
    Backend-->>Frontend: 6. Return access token
    Frontend->>Frontend: 7. Store in localStorage
    Frontend-->>User: 8. Redirect to dashboard

    Note over Frontend,Backend: Subsequent requests
    User->>Frontend: 9. Access protected page
    Frontend->>Backend: 10. Request with Bearer token
    Backend->>Backend: 11. Validate JWT
    Backend-->>Frontend: 12. Return data
```

### Security Layers

```mermaid
flowchart TB
    subgraph Edge["Edge Security"]
        HTTPS["HTTPS/TLS 1.3"]
        CORS["CORS Policy"]
    end

    subgraph App["Application Security"]
        Auth["JWT Authentication"]
        Validation["Input Validation<br/>Pydantic"]
        SQLi["SQL Injection Prevention<br/>SQLAlchemy"]
    end

    subgraph Data["Data Security"]
        Encryption["Encryption at Rest"]
        PrivateNet["Private Networking"]
        IAM["IAM / Service Accounts"]
    end

    HTTPS --> CORS
    CORS --> Auth
    Auth --> Validation
    Validation --> SQLi
    SQLi --> Encryption
    Encryption --> PrivateNet
```

### API Security

| Layer | Protection |
|-------|------------|
| Transport | HTTPS with TLS 1.3 |
| Origin | CORS restricted to allowed origins |
| Rate Limiting | Redis-based request throttling |
| Authentication | JWT tokens (7-day expiry) |
| Authorization | Role-based access control |
| Input | Pydantic schema validation |
| Database | SQLAlchemy parameterized queries |

### Storage Security

| Environment | Authentication | Access Control |
|-------------|----------------|----------------|
| **Local (MinIO)** | Access keys | Bucket policies |
| **Production (GCS)** | Service account | IAM roles |
| **Browser Access** | Presigned URLs | Time-limited (15 min) |

## Deployment Architecture

### Local Development

```mermaid
flowchart TB
    subgraph Docker["Docker Compose"]
        FE["frontend:3000"]
        BE["backend:8000"]
        DB["postgres:5432"]
        REDIS["redis:6379"]
        MINIO["minio:9000/9001"]
    end

    FE --> BE
    BE --> DB
    BE --> REDIS
    BE --> MINIO
```

### Production (GCP)

```mermaid
flowchart TB
    subgraph Internet
        Users["Users"]
        DNS["DNS"]
    end

    subgraph GCP["Google Cloud Platform"]
        LB["Load Balancer<br/>+ Managed SSL"]

        subgraph CloudRun["Cloud Run"]
            FE["Frontend Service"]
            BE["Backend Service"]
        end

        subgraph Private["Private Network"]
            SQL["Cloud SQL"]
            Redis["Memorystore"]
        end

        GCS["Cloud Storage"]
        Vertex["Vertex AI"]
    end

    Users --> DNS
    DNS --> LB
    LB --> FE
    LB --> BE
    BE --> SQL
    BE --> Redis
    BE --> GCS
    BE --> Vertex
```

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 14 | React framework with App Router |
| | TypeScript | Type safety |
| | Tailwind CSS | Utility-first styling |
| | React Query | Data fetching & caching |
| | pnpm | Package management |
| **Backend** | FastAPI | Async Python web framework |
| | SQLAlchemy 2.0 | ORM |
| | Pydantic v2 | Data validation |
| | UV | Fast package management |
| **AI** | Google Gemini | Multimodal AI (vision + text) |
| | Vertex AI | Managed AI platform |
| **Database** | PostgreSQL 15 | Primary data store |
| | Redis 7 | Caching & sessions |
| **Storage** | MinIO | Local S3-compatible storage |
| | Google Cloud Storage | Production file storage |
| **Infrastructure** | Docker | Containerization |
| | Terraform | Infrastructure as Code |
| | GCP Cloud Run | Serverless containers |
