# Database & Models

AppArt Agent uses PostgreSQL with SQLAlchemy ORM for data persistence.

## Database Connection

Configuration in `app/core/database.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

## Models

### User

```python
# app/models/user.py
class User(Base):
    __tablename__ = "users"

    id: int                    # Primary key
    email: str                 # Unique, indexed
    hashed_password: str       # bcrypt hash
    full_name: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    # Relationships
    properties: List[Property]
```

### Property

```python
# app/models/property.py
class Property(Base):
    __tablename__ = "properties"

    id: int
    user_id: int               # Foreign key
    address: str
    postal_code: str           # Indexed
    city: str
    department: str
    asking_price: float
    surface_area: float
    property_type: str         # apartment, house
    rooms: int
    floor: int
    building_floors: int       # Total floors in the building
    building_year: int
    created_at: datetime
    updated_at: datetime

    # Relationships
    user: User
    documents: List[Document]
    photos: List[Photo]
```

### Document

```python
# app/models/document.py
class Document(Base):
    __tablename__ = "documents"

    id: int
    property_id: int           # Foreign key
    filename: str
    original_filename: str
    document_type: str         # pv_ag, diags, taxe_fonciere, charges, other
    status: str                # pending, processing, analyzed, failed
    file_hash: str             # SHA-256 for deduplication
    storage_key: str           # Storage object key (renamed from minio_key)
    storage_bucket: str        # Storage bucket name (renamed from minio_bucket)
    analysis_result: JSON      # Structured analysis
    created_at: datetime
    updated_at: datetime

    # Relationships
    property: Property
```

### Photo

```python
# app/models/photo.py
class Photo(Base):
    __tablename__ = "photos"

    id: int
    property_id: int
    filename: str
    storage_key: str           # Storage object key (renamed from minio_key)
    storage_bucket: str        # Storage bucket name (renamed from minio_bucket)
    room_type: str             # living_room, bedroom, kitchen, etc.
    promoted_redesign_id: int  # FK to photo_redesigns (featured redesign)
    created_at: datetime

    # Relationships
    property: Property
    redesigns: List[PhotoRedesign]
    promoted_redesign: PhotoRedesign  # The promoted/featured redesign

class PhotoRedesign(Base):
    __tablename__ = "photo_redesigns"

    id: int
    photo_id: int
    redesign_uuid: str         # Unique identifier
    style: str
    preferences: JSON
    status: str                # pending, generating, completed, failed
    storage_key: str           # Storage object key (renamed from minio_key)
    storage_bucket: str        # Storage bucket name (renamed from minio_bucket)
    created_at: datetime
```

### DVFRecord

```python
# app/models/property.py
class DVFRecord(Base):
    __tablename__ = "dvf_records"

    id: int
    sale_date: date
    sale_price: float
    address: str               # Indexed (GIN trigram)
    postal_code: str           # Indexed
    city: str
    property_type: str
    surface_area: float
    rooms: int
    price_per_sqm: float       # Calculated
    data_year: int             # Import year
    import_batch_id: str       # For rollback

    # Indexes
    # - postal_code + property_type + address (composite)
    # - address (GIN trigram for fuzzy search)
```

### DocumentSummary

```python
# app/models/analysis.py
class DocumentSummary(Base):
    __tablename__ = "document_summaries"

    id: int
    property_id: int           # Foreign key
    overall_summary: str
    total_annual_cost: float
    total_one_time_cost: float
    risk_level: str            # low, medium, high
    recommendations: JSON
    synthesis_data: JSON       # Full synthesis result
    last_updated: datetime
```

## Entity Relationship Diagram

```mermaid
erDiagram
    User ||--o{ Property : owns
    Property ||--o{ Document : has
    Property ||--o{ Photo : has
    Property ||--o| DocumentSummary : has
    Photo ||--o{ PhotoRedesign : has
    Photo ||--o| PhotoRedesign : promotes
    DVFImport ||--o{ DVFRecord : contains

    User {
        int id PK
        string email UK
        string hashed_password
        string full_name
        boolean is_active
        datetime created_at
    }

    Property {
        int id PK
        int user_id FK
        string address
        string postal_code
        string city
        string department
        float asking_price
        float surface_area
        string property_type
        int rooms
        int floor
        int building_floors
        int building_year
    }

    Document {
        int id PK
        int property_id FK
        string filename
        string document_type
        string status
        string file_hash
        string storage_key
        string storage_bucket
        json analysis_result
    }

    Photo {
        int id PK
        int property_id FK
        string filename
        string storage_key
        string storage_bucket
        string room_type
        int promoted_redesign_id FK
    }

    PhotoRedesign {
        int id PK
        int photo_id FK
        string redesign_uuid
        string style
        json preferences
        string status
        string storage_key
        string storage_bucket
    }

    DocumentSummary {
        int id PK
        int property_id FK
        string overall_summary
        float total_annual_cost
        float total_one_time_cost
        string risk_level
        json synthesis_data
        json user_overrides
    }

    DVFRecord {
        int id PK
        date sale_date
        float sale_price
        string address
        string postal_code
        string import_batch_id FK
    }

    DVFImport {
        string batch_id PK
        string source_file
        int data_year
        string status
        int total_records
    }
```

## Migrations

Managed with Alembic:

```bash
# Create migration
docker-compose exec backend alembic revision --autogenerate -m "Add new field"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Rollback one migration
docker-compose exec backend alembic downgrade -1

# Show current version
docker-compose exec backend alembic current

# Show migration history
docker-compose exec backend alembic history
```

### Migration Files

```text
alembic/versions/
├── 30257fbe1e49_create_initial_tables.py
├── a1b2c3d4e5f6_add_minio_temporal_columns.py
├── b2c3d4e5f6g7_add_langgraph_fields.py
├── 19c3bf31bde4_add_photo_and_photoredesign_models.py
├── c4d5e6f7g8h9_add_redesign_uuid_to_photo_redesigns.py
├── 25ffc9523881_merge_photo_redesign_uuid_heads.py
├── i0j1k2l3m4n5_rename_minio_to_storage.py       # Rename minio_key/bucket → storage_key/bucket
├── j1k2l3m4n5o6_add_promoted_redesign_to_photos.py  # Add promoted_redesign_id FK
└── k2l3m4n5o6p7_add_building_floors_to_properties.py  # Add building_floors column
```

## Indexes

### Performance Indexes

```sql
-- DVF address search (trigram for fuzzy matching)
CREATE INDEX idx_dvf_address_gin ON dvf_records
USING GIN (address gin_trgm_ops);

-- Common query pattern
CREATE INDEX idx_dvf_postal_type_addr ON dvf_records
(postal_code, property_type, address);

-- Date range queries
CREATE INDEX idx_dvf_sale_date ON dvf_records (sale_date);

-- Document lookup
CREATE INDEX idx_documents_property ON documents (property_id);
CREATE INDEX idx_documents_status ON documents (status);
```

### Unique Constraints

```sql
-- Prevent duplicate DVF records
ALTER TABLE dvf_records ADD CONSTRAINT uq_dvf_sale
UNIQUE (sale_date, sale_price, address, postal_code, surface_area);

-- Prevent duplicate documents (by hash)
ALTER TABLE documents ADD CONSTRAINT uq_doc_hash
UNIQUE (property_id, file_hash);
```

## Querying Examples

### Find Properties

```python
from app.models.property import Property
from sqlalchemy.orm import Session

def get_user_properties(db: Session, user_id: int):
    return db.query(Property).filter(
        Property.user_id == user_id
    ).all()
```

### DVF Search

```python
from app.models.property import DVFRecord
from sqlalchemy import func

def search_dvf(db: Session, address: str, postal_code: str):
    return db.query(DVFRecord).filter(
        DVFRecord.postal_code == postal_code,
        func.similarity(DVFRecord.address, address) > 0.3
    ).order_by(
        func.similarity(DVFRecord.address, address).desc()
    ).limit(100).all()
```

### Aggregations

```python
from sqlalchemy import func

def get_price_stats(db: Session, postal_code: str, year: int):
    return db.query(
        func.count(DVFRecord.id).label('count'),
        func.avg(DVFRecord.price_per_sqm).label('avg_price'),
        func.min(DVFRecord.price_per_sqm).label('min_price'),
        func.max(DVFRecord.price_per_sqm).label('max_price')
    ).filter(
        DVFRecord.postal_code == postal_code,
        DVFRecord.data_year == year
    ).first()
```

## Database Management

### Backup

```bash
# Create backup
docker-compose exec db pg_dump -U appart appart_agent > backup.sql

# Restore backup
docker-compose exec -T db psql -U appart appart_agent < backup.sql
```

### Query Stats

```sql
-- Check table sizes
SELECT
    relname as table_name,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

-- Check index usage
SELECT
    indexrelname as index_name,
    idx_scan as times_used
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```
