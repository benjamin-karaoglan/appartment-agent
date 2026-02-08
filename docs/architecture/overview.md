# System Overview

## High-Level Architecture

```mermaid
flowchart TB
    subgraph ClientLayer["Client Layer"]
        Browser["Web Browser<br/>Dashboard | Documents | Photos"]
    end

    subgraph FrontendLayer["Frontend Layer - Next.js 14"]
        subgraph Pages["Pages (App Router)"]
            P1["Dashboard<br/>Synthesis previews"]
            P2["Properties<br/>Inline editing"]
            P3["Documents<br/>Multi-phase processing"]
            P4["Photos<br/>Redesign + promote"]
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
            E2["/api/properties<br/>CRUD + with-synthesis"]
            E3["/api/documents<br/>Upload, bulk ops, synthesis"]
            E4["/api/analysis<br/>Price trends"]
            E5["/api/photos<br/>Redesign + promote"]
        end

        subgraph Services["Service Layer"]
            S1["AI Services<br/>Native PDF | Thinking | Synthesis"]
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
            Locale["[locale] Layout"]
            Pages["Page Components"]
        end

        subgraph Auth["Authentication"]
            BetterAuth["Better Auth<br/>(API Routes)"]
            AuthContext["Auth Context"]
        end

        subgraph State["State Management"]
            ReactQuery["React Query Cache"]
            i18n["next-intl<br/>FR / EN"]
        end

        subgraph UI["UI Layer"]
            Tailwind["Tailwind CSS"]
            Components["Component Library"]
        end
    end

    Layout --> Locale --> Pages
    Pages --> Auth
    Pages --> State
    Pages --> UI
```

| Directory | Purpose |
|-----------|---------|
| `src/app/[locale]/` | Locale-scoped App Router pages |
| `src/app/api/auth/` | Better Auth API route handler |
| `src/components/` | Reusable React components |
| `src/contexts/` | React context providers (Auth) |
| `src/i18n/` | Internationalization config and routing |
| `src/lib/` | Utilities, API client, and auth config |
| `src/types/` | TypeScript type definitions |
| `messages/` | Translation files (en.json, fr.json) |

**Key Technologies**:

- **React 18** with Server Components
- **Better Auth** for authentication (email/password + Google OAuth)
- **next-intl** for internationalization (FR/EN)
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
| `users` | ~100s | User accounts and profile data |
| `ba_user` | ~100s | Better Auth user accounts |
| `ba_session` | ~100s | Better Auth active sessions |
| `ba_account` | ~100s | Better Auth OAuth provider links |
| `properties` | ~100s | Properties and their metadata |
| `documents` | ~1000s | Documents and analysis results (5 categories) |
| `document_summaries` | ~100s | Cross-document synthesis with user overrides |
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

### Authentication Flow (Better Auth)

Authentication is handled by [Better Auth](https://www.better-auth.com/) on the frontend via Next.js API routes. The backend validates sessions by checking cookies against the `ba_session` database table.

```mermaid
sequenceDiagram
    participant User as User Browser
    participant FE as Frontend (Next.js)
    participant Auth as API Route (/api/auth/*)
    participant DB as PostgreSQL
    participant BE as Backend (FastAPI)

    rect rgb(230, 245, 255)
        Note over User,DB: Registration / Login
        User->>FE: 1. Enter credentials (or click Google OAuth)
        FE->>Auth: 2. POST /api/auth/sign-in
        Auth->>DB: 3. Verify credentials (bcrypt)
        Auth->>DB: 4. Create session in ba_session table
        Auth-->>FE: 5. Set HTTP-only cookie (better-auth.session_token)
        FE-->>User: 6. Redirect to dashboard
    end

    rect rgb(230, 255, 230)
        Note over User,BE: Authenticated API Requests
        User->>FE: 7. Access protected page
        FE->>BE: 8. Request with session cookie
        BE->>DB: 9. Validate cookie against ba_session
        BE->>DB: 10. Check session expiry + user active
        BE-->>FE: 11. Return protected data
        FE-->>User: 12. Display content
    end
```

**Key differences from legacy JWT:**

- No tokens stored in localStorage — HTTP-only cookies only
- Session state lives in PostgreSQL (`ba_session` table), not in the token
- Google OAuth supported as an optional provider
- Backend validates by querying the database, not by verifying a JWT signature

### Security Layers

```mermaid
flowchart TB
    subgraph Edge["Edge Security"]
        HTTPS["HTTPS/TLS 1.3"]
        CORS["CORS Policy"]
    end

    subgraph App["Application Security"]
        Auth["Better Auth Sessions<br/>(HTTP-only cookies)"]
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
| Authentication | Better Auth session cookies (7-day expiry) |
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
