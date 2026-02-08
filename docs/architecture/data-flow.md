# Data Flow

This document describes how data flows through the AppArt Agent system for key operations.

## Document Upload and Analysis

The bulk document upload flow demonstrates the multi-phase async processing architecture. The frontend tracks three distinct phases: Upload, Analysis, and Synthesis.

```mermaid
sequenceDiagram
    participant User as User Browser
    participant FE as Frontend (Next.js)
    participant BE as Backend (FastAPI)
    participant Store as Storage (MinIO/GCS)
    participant AI as AI (Gemini)
    participant DB as PostgreSQL

    rect rgb(230, 245, 255)
        Note over User,BE: Phase 1 - Upload
        User->>FE: 1. Select files (drag & drop)
        FE->>FE: 2. Show upload progress indicator
        FE->>BE: 3. POST /documents/bulk-upload
        BE->>Store: 4. Store files with SHA-256 hash
        BE->>DB: 5. Create document records
        BE-->>FE: 6. Return workflow_id
    end

    rect rgb(255, 245, 230)
        Note over BE,AI: Phase 2 - Analysis (background thread)
        BE->>BE: 7. Prepare PDFs (extract text + metadata)
        BE->>AI: 8. Classify via native PDF input
        AI-->>BE: 9. Document types (5 categories)
        BE->>AI: 10. Parallel analysis with thinking enabled
        AI-->>BE: 11. Structured analysis results
        BE->>DB: 12. Save per-document results
    end

    rect rgb(255, 230, 255)
        Note over BE,AI: Phase 3 - Synthesis
        BE->>AI: 13. Cross-document synthesis
        AI-->>BE: 14. Costs, risks, tantiemes, themes, action items
        BE->>DB: 15. Save synthesis (preserve user overrides)
    end

    rect rgb(230, 255, 230)
        Note over User,FE: Results
        FE->>BE: 16. Poll GET /documents/bulk-status/{id}
        BE-->>FE: 17. Status: complete + results
        FE-->>User: 18. Display analysis with expandable breakdowns
    end
```

### Processing Stages

```mermaid
flowchart LR
    subgraph Upload["1. Upload"]
        A["Files<br/>(PDF, Images)"]
        B["Multipart<br/>Form Data"]
    end

    subgraph Storage["2. Storage"]
        C["SHA-256<br/>Dedup Hash"]
        D["MinIO/GCS<br/>Object Store"]
    end

    subgraph Preparation["3. PDF Preparation"]
        E["Extract text<br/>(PyMuPDF)"]
        F["Gather metadata<br/>(pages, size)"]
    end

    subgraph Classification["4. Classification"]
        G["Native PDF<br/>to Gemini"]
        H["Document<br/>Category"]
    end

    subgraph Analysis["5. Analysis"]
        I["Type-specific<br/>Prompts + Thinking"]
        J["Parallel via<br/>asyncio.gather()"]
        K["Structured<br/>JSON Results"]
    end

    subgraph Synthesis["6. Synthesis"]
        L["Cost Breakdown<br/>(annual + one-time)"]
        M["Tantiemes<br/>Calculation"]
        N["Cross-doc Themes<br/>+ Action Items"]
        O["Risk Assessment<br/>+ Confidence Score"]
    end

    A --> B --> C --> D
    D --> E --> F
    F --> G --> H
    H --> I --> J --> K
    K --> L --> M --> N --> O
```

### Document Type Detection

Documents are classified into 5 categories using native PDF input to Gemini:

```mermaid
flowchart TD
    Input["Native PDF<br/>(sent directly to Gemini)"]

    Input --> Gemini["Gemini Classification"]

    Gemini --> PV["pv_ag<br/>Assembly minutes"]
    Gemini --> Diags["diags<br/>DPE, amiante, plomb,<br/>electric, gas, etc."]
    Gemini --> Tax["taxe_fonciere<br/>Property tax"]
    Gemini --> Charges["charges<br/>Copropriete fees"]
    Gemini --> Other["other<br/>Rules, contracts,<br/>insurance, etc."]
```

### Synthesis Regeneration

Synthesis is automatically regenerated when documents are added or removed. It can also be manually triggered. User overrides (tantiemes, cost adjustments) are preserved across regenerations.

```mermaid
flowchart TD
    Trigger["Trigger:<br/>Upload / Delete / Manual"]
    Trigger --> Fetch["Fetch all analyzed<br/>documents for property"]
    Fetch --> Check{"Any analyzed<br/>documents?"}
    Check -->|No| Clear["Clear synthesis"]
    Check -->|Yes| LoadOverrides["Load existing<br/>user overrides"]
    LoadOverrides --> Synthesize["Run AI synthesis<br/>with all document summaries"]
    Synthesize --> Merge["Merge user overrides<br/>into synthesis_data"]
    Merge --> Save["Save to DocumentSummary"]
```

## Price Analysis Flow

```mermaid
sequenceDiagram
    participant User as User Browser
    participant FE as Frontend (Next.js)
    participant BE as Backend (FastAPI)
    participant DB as PostgreSQL (DVF)
    participant Cache as Redis

    User->>FE: 1. Enter property address
    FE->>BE: 2. GET /analysis/price?address=...

    BE->>Cache: 3. Check cache
    alt Cache hit
        Cache-->>BE: Cached results
    else Cache miss
        BE->>DB: 4. Query DVF records
        Note over DB: 5.4M+ transactions
        DB-->>BE: 5. Raw transaction data
        BE->>BE: 6. Apply IQR filtering
        BE->>BE: 7. Calculate statistics
        BE->>BE: 8. Project trends
        BE->>Cache: 9. Cache results (1hr TTL)
    end

    BE-->>FE: 10. Price analysis JSON
    FE-->>User: 11. Display charts & insights
```

### DVF Query Pipeline

```mermaid
flowchart LR
    subgraph Input["Query Input"]
        Address["Address<br/>(fuzzy match)"]
        Params["Filters<br/>(date, type, area)"]
    end

    subgraph Query["Database Query"]
        Search["PostgreSQL<br/>Full-text search"]
        Filter["WHERE clauses"]
        Sort["ORDER BY date"]
    end

    subgraph Processing["Data Processing"]
        IQR["IQR Outlier<br/>Removal"]
        Stats["Statistics<br/>(mean, median, std)"]
        Trend["Trend<br/>Calculation"]
    end

    subgraph Output["Response"]
        Simple["Simple Analysis<br/>(exact matches)"]
        Market["Market Analysis<br/>(area comparison)"]
        Projection["Price Projection<br/>(future estimate)"]
    end

    Address --> Search
    Params --> Filter
    Search --> Filter --> Sort
    Sort --> IQR --> Stats --> Trend
    Trend --> Simple
    Trend --> Market
    Trend --> Projection
```

### Analysis Types

| Type | Data Source | Purpose | Cache TTL |
|------|-------------|---------|-----------|
| **Simple** | Exact address matches | Historical sales at property | 1 hour |
| **Trend** | Neighboring properties | Price evolution over time | 1 hour |
| **Market** | Area-wide data | Comparative market analysis | 1 hour |
| **Projection** | Trend + Market | Estimated future price | 1 hour |

## Photo Redesign Flow

```mermaid
sequenceDiagram
    participant User as User Browser
    participant FE as Frontend (Next.js)
    participant BE as Backend (FastAPI)
    participant Store as Storage (MinIO/GCS)
    participant AI as AI (Gemini)
    participant DB as PostgreSQL

    rect rgb(230, 245, 255)
        Note over User,Store: Upload Phase
        User->>FE: 1. Upload apartment photo
        FE->>BE: 2. POST /photos/upload
        BE->>Store: 3. Store original image
        BE->>DB: 4. Create photo record
        BE-->>FE: 5. Return photo_id + presigned URL
        FE-->>User: 6. Display uploaded photo
    end

    rect rgb(255, 245, 230)
        Note over User,AI: Redesign Phase
        User->>FE: 7. Select style (modern, scandinavian, etc.)
        FE->>BE: 8. POST /photos/{id}/redesign
        BE->>Store: 9. Fetch original image
        BE->>AI: 10. Generate redesign (Gemini)
        AI-->>BE: 11. Generated image bytes
        BE->>Store: 12. Store redesigned image
        BE->>DB: 13. Update photo record
        BE-->>FE: 14. Return presigned URL
    end

    rect rgb(230, 255, 230)
        Note over User,FE: Display Phase
        FE->>Store: 15. Fetch via presigned URL
        Store-->>FE: 16. Image bytes
        FE-->>User: 17. Display side-by-side comparison
    end

    rect rgb(255, 255, 230)
        Note over User,BE: Promote Phase (optional)
        User->>FE: 18. Click "Promote" on a redesign
        FE->>BE: 19. PATCH /photos/{id}/promote/{redesign_id}
        BE->>DB: 20. Set photo.promoted_redesign_id
        BE-->>FE: 21. Updated photo with promoted_redesign
        FE-->>User: 22. Show promoted badge + display on property overview
    end
```

### Redesign Styles

```mermaid
flowchart LR
    Original["Original Photo"]

    Original --> Modern["Modern<br/>Clean lines, contemporary"]
    Original --> Scandi["Scandinavian<br/>Light wood, minimal"]
    Original --> Industrial["Industrial<br/>Exposed brick, metal"]
    Original --> Bohemian["Bohemian<br/>Colorful, eclectic"]
    Original --> Classic["Classic<br/>Traditional, rich colors"]
```

## Authentication Flow (Better Auth)

Authentication is handled by [Better Auth](https://www.better-auth.com/) on the frontend via Next.js API routes. The backend validates sessions by checking the `better-auth.session_token` cookie against the `ba_session` database table.

```mermaid
sequenceDiagram
    participant User as User Browser
    participant FE as Frontend (Next.js)
    participant Auth as API Route (/api/auth/*)
    participant DB as PostgreSQL (ba_* tables)
    participant BE as Backend (FastAPI)

    rect rgb(230, 245, 255)
        Note over User,DB: Registration (Email/Password)
        User->>FE: 1. Fill registration form
        FE->>Auth: 2. POST /api/auth/sign-up/email
        Auth->>Auth: 3. Hash password (bcrypt)
        Auth->>DB: 4. Create ba_user + ba_account records
        Auth->>DB: 5. Create ba_session record
        Auth-->>FE: 6. Set HTTP-only cookie
        FE-->>User: 7. Redirect to dashboard
    end

    rect rgb(255, 245, 230)
        Note over User,DB: Login (Email/Password or Google OAuth)
        User->>FE: 8. Enter credentials or click "Sign in with Google"
        FE->>Auth: 9. POST /api/auth/sign-in/email (or OAuth redirect)
        Auth->>DB: 10. Verify credentials
        Auth->>DB: 11. Create or update ba_session
        Auth-->>FE: 12. Set HTTP-only cookie (better-auth.session_token)
        FE-->>User: 13. Redirect to dashboard
    end

    rect rgb(230, 255, 230)
        Note over User,BE: Authenticated API Requests
        User->>FE: 14. Access protected page
        FE->>BE: 15. GET /api/... (cookie sent automatically)
        BE->>DB: 16. Query ba_session WHERE token = cookie
        BE->>BE: 17. Check session expiry + user active
        BE-->>FE: 18. Return protected data
        FE-->>User: 19. Display content
    end
```

### Session Cookie Structure

```mermaid
flowchart LR
    subgraph Cookie["better-auth.session_token"]
        Token["Session Token<br/>(random string)"]
        Dot["."]
        Signature["Signature<br/>(HMAC verification)"]
    end

    Token --> Dot --> Signature
```

The backend extracts only the token part (before the `.`) and looks it up in the `ba_session` table. Sessions expire after 7 days.

## DVF Data Import Flow

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant BE as Backend
    participant FS as File System
    participant DB as PostgreSQL

    Admin->>BE: 1. Trigger import (CLI or API)
    BE->>FS: 2. Read DVF CSV files
    Note over FS: Files are pipe-delimited (|)

    loop For each chunk (30k records)
        BE->>BE: 3. Parse CSV chunk
        BE->>BE: 4. Transform fields
        BE->>BE: 5. Generate SHA-256 hash
        BE->>DB: 6. Bulk upsert (ON CONFLICT)
        DB-->>BE: 7. Acknowledge
        BE->>BE: 8. Log progress
    end

    BE-->>Admin: 9. Import complete (5.4M+ records)
```

### DVF Data Pipeline

```mermaid
flowchart TB
    subgraph Source["Data Source"]
        CSV["DVF CSV Files<br/>(data.gouv.fr)"]
    end

    subgraph Transform["Transformation"]
        Parse["Parse pipe-delimited"]
        Clean["Clean & normalize"]
        Hash["SHA-256 dedup hash"]
        Chunk["Split into 30k chunks"]
    end

    subgraph Load["Database Load"]
        Upsert["Bulk UPSERT<br/>(ON CONFLICT DO UPDATE)"]
        Index["Update indexes"]
    end

    subgraph Verify["Verification"]
        Count["Record count"]
        Sample["Sample queries"]
    end

    CSV --> Parse --> Clean --> Hash --> Chunk
    Chunk --> Upsert --> Index
    Index --> Count --> Sample
```

## Data Consistency

### Transaction Boundaries

```mermaid
flowchart TD
    subgraph DocumentUpload["Document Upload"]
        D1["Create record"] --> D2["Store file"]
        D2 --> D3["Update status"]
        Note1["Single transaction<br/>Rollback on failure"]
    end

    subgraph BulkProcess["Bulk Processing"]
        B1["Process doc 1"] --> B2["Process doc 2"]
        B2 --> B3["Process doc N"]
        Note2["Per-document transactions<br/>Partial success possible"]
    end

    subgraph DVFImport["DVF Import"]
        I1["Chunk 1 (30k)"] --> I2["Chunk 2 (30k)"]
        I2 --> I3["Chunk N"]
        Note3["Per-chunk transactions<br/>Resume on failure"]
    end
```

### Caching Strategy

```mermaid
flowchart LR
    subgraph Request["Incoming Request"]
        API["API Call"]
    end

    subgraph CacheLayer["Cache Layer (Redis)"]
        Check{"Cache<br/>Hit?"}
        Get["Return cached"]
        Miss["Query DB"]
        Set["Cache result"]
    end

    subgraph Database["PostgreSQL"]
        Query["Execute query"]
    end

    API --> Check
    Check -->|"Yes"| Get
    Check -->|"No"| Miss
    Miss --> Query --> Set --> Get
```

| Data Type | Cache Location | TTL | Invalidation |
|-----------|---------------|-----|--------------|
| User sessions | Redis | 7 days | On logout |
| DVF queries | Redis | 1 hour | Time-based |
| Document metadata | PostgreSQL | N/A | On update |
| File content | MinIO/GCS | N/A | Manual delete |
| AI analysis results | PostgreSQL | N/A | On re-analysis |

## Error Handling Flow

```mermaid
flowchart TD
    Request["API Request"]

    Request --> Validation{"Input<br/>Valid?"}
    Validation -->|"No"| Error400["400 Bad Request"]
    Validation -->|"Yes"| Auth{"User<br/>Authenticated?"}

    Auth -->|"No"| Error401["401 Unauthorized"]
    Auth -->|"Yes"| Process["Process Request"]

    Process --> DB{"Database<br/>Error?"}
    DB -->|"Yes"| Retry{"Retryable?"}
    Retry -->|"Yes"| Process
    Retry -->|"No"| Error500["500 Internal Error"]

    DB -->|"No"| AI{"AI<br/>Error?"}
    AI -->|"Yes"| Fallback["Return partial result"]
    AI -->|"No"| Success["200 OK"]

    Error400 --> Log["Log error"]
    Error401 --> Log
    Error500 --> Log
    Fallback --> Log
    Success --> Log
```

## Real-time Updates (Future)

```mermaid
sequenceDiagram
    participant User as User Browser
    participant FE as Frontend
    participant BE as Backend
    participant Worker as Background Worker

    User->>FE: Start document processing
    FE->>BE: POST /documents/process
    BE->>Worker: Queue job
    BE-->>FE: Return job_id

    loop Until complete
        FE->>BE: GET /jobs/{id}/status
        BE-->>FE: {status, progress}
        FE-->>User: Update progress bar
    end

    Worker-->>BE: Job complete
    BE-->>FE: Final result
    FE-->>User: Display results
```
