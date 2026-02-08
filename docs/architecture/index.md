# Architecture

This section covers the system design and architecture of AppArt Agent.

## Overview

```mermaid
flowchart TB
    subgraph Frontend["Frontend (Next.js 14)"]
        UI["React UI"]
    end

    subgraph Backend["Backend (FastAPI)"]
        API["REST API"]
        Services["Services"]
    end

    subgraph Data["Data Layer"]
        DB[(PostgreSQL)]
        Cache[(Redis)]
        Storage[(MinIO/GCS)]
    end

    subgraph External["External"]
        AI["Gemini AI"]
    end

    UI --> API
    API --> Services
    Services --> DB
    Services --> Cache
    Services --> Storage
    Services --> AI
```

AppArt Agent follows a modern microservices architecture with clear separation of concerns:

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 14 | React app with App Router |
| **Backend** | FastAPI | Async REST API |
| **Database** | PostgreSQL 15 | Primary data store (5.4M+ DVF records) |
| **Cache** | Redis 7 | Sessions and query caching |
| **Storage** | MinIO / GCS | Documents and photos |
| **AI** | Google Gemini | Document analysis, image generation |

## Sections

| Guide | Description |
|-------|-------------|
| [System Overview](overview.md) | High-level architecture, components, and security |
| [Data Flow](data-flow.md) | How data moves through the system for key operations |

## Design Principles

### 1. Separation of Concerns

```mermaid
flowchart LR
    subgraph Layers["Application Layers"]
        API["API Layer<br/>Validation, Routing"]
        Service["Service Layer<br/>Business Logic"]
        Data["Data Layer<br/>Models, Storage"]
    end

    API --> Service --> Data
```

Each layer has a specific responsibility:

- **API Layer**: Request handling, validation, routing
- **Service Layer**: Business logic, AI orchestration
- **Data Layer**: Database models, storage operations

### 2. Async-First Processing

```mermaid
flowchart LR
    Request["Request"]
    Queue["Background<br/>Processing"]
    Response["Immediate<br/>Response"]
    Result["Async<br/>Result"]

    Request --> Queue
    Request --> Response
    Queue --> Result
```

Background processing for:

- Document analysis (native PDF classification + extraction with thinking)
- Bulk uploads with multi-phase tracking (upload, analysis, synthesis)
- Cross-document synthesis with cost breakdowns and tantiemes
- Image generation (photo redesigns)
- Automatic synthesis regeneration on document changes

### 3. Multi-Backend Storage

```mermaid
flowchart TB
    App["Application"]

    subgraph StorageInterface["Storage Interface"]
        Abstract["AbstractStorage"]
    end

    subgraph Backends["Storage Backends"]
        MinIO["MinIO<br/>(Local Dev)"]
        GCS["Google Cloud Storage<br/>(Production)"]
    end

    App --> Abstract
    Abstract --> MinIO
    Abstract --> GCS
```

Abstracted storage interface supporting:

- **MinIO** for local development (S3-compatible)
- **Google Cloud Storage** for production (managed)

### 4. Environment Parity

```mermaid
flowchart LR
    subgraph Local["Local Development"]
        Docker["Docker Compose"]
        Impersonation["GCP Impersonation"]
    end

    subgraph Production["Production (GCP)"]
        CloudRun["Cloud Run"]
        CloudSQL["Cloud SQL"]
        GCS["Cloud Storage"]
    end

    Docker --> CloudRun
    Impersonation --> Production
```

Two modes for local development:

- **Docker Compose**: Full stack with MinIO
- **GCP Impersonation**: Real GCS/Vertex AI with local code

## Quick Links

- [System Overview →](overview.md)
- [Data Flow →](data-flow.md)
- [Deployment Options →](../deployment/index.md)
