"""Property and DVF record models."""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, Text, Index, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Property(Base):
    """Property model for storing apartment information."""

    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Address information
    address = Column(String, nullable=False)
    postal_code = Column(String)
    city = Column(String)
    department = Column(String)

    # Property details
    asking_price = Column(Float)
    surface_area = Column(Float)  # in m²
    rooms = Column(Integer)
    property_type = Column(String)  # Appartement, Maison, etc.
    floor = Column(Integer)
    building_year = Column(Integer)

    # Analysis results
    estimated_value = Column(Float)
    price_per_sqm = Column(Float)
    market_comparison_score = Column(Float)  # 0-100
    recommendation = Column(String)  # "Good deal", "Fair price", "Overpriced", etc.

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="properties")
    documents = relationship("Document", back_populates="property", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="property", cascade="all, delete-orphan")


class DVFRecord(Base):
    """DVF (Demandes de Valeurs Foncières) records from French government data."""

    __tablename__ = "dvf_records"

    id = Column(Integer, primary_key=True, index=True)

    # Transaction information
    sale_date = Column(Date, index=True)
    sale_price = Column(Float)

    # Property information
    address = Column(String)
    postal_code = Column(String, index=True)
    city = Column(String, index=True)
    department = Column(String, index=True)

    # Property details
    property_type = Column(String)  # Maison, Appartement, etc.
    surface_area = Column(Float)
    rooms = Column(Integer)
    land_surface = Column(Float)

    # Calculated fields
    price_per_sqm = Column(Float)

    # Raw data for reference
    raw_data = Column(Text)  # JSON string of full record

    # Versioning and tracking fields (for production-ready import management)
    data_year = Column(Integer, index=True)  # Year of DVF dataset (e.g., 2023)
    source_file = Column(String)  # Original filename
    source_file_hash = Column(String(64))  # SHA256 hash of source file
    import_batch_id = Column(String(36), index=True)  # UUID for this import batch
    imported_at = Column(DateTime, default=datetime.utcnow)  # When this record was imported

    # Transaction grouping (multiple properties sold together)
    transaction_group_id = Column(String(32), index=True)  # Hash of (sale_date, price, address, postal)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Composite indexes for query optimization
    __table_args__ = (
        # Unique constraint for deduplication - DVF business key
        Index('idx_dvf_unique_sale',
              'sale_date', 'sale_price', 'address', 'postal_code', 'surface_area',
              unique=True),

        # Composite indexes for common query patterns
        Index('idx_dvf_postal_type_address', 'postal_code', 'property_type', 'address'),
        Index('idx_dvf_date_postal_type', 'sale_date', 'postal_code', 'property_type'),
        Index('idx_dvf_postal_type_surface', 'postal_code', 'property_type', 'surface_area'),

        # GIN index for fast ILIKE queries on address (requires pg_trgm extension)
        Index('idx_dvf_address_gin', 'address',
              postgresql_using='gin',
              postgresql_ops={'address': 'gin_trgm_ops'}),

        # Partial index for price_per_sqm (only non-null positive values)
        Index('idx_dvf_price_per_sqm', 'price_per_sqm',
              postgresql_where='price_per_sqm > 0'),
    )


class DVFImport(Base):
    """Track DVF import operations for audit trail and rollback capability."""

    __tablename__ = "dvf_imports"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    source_file = Column(String, nullable=False)  # Filename
    source_file_hash = Column(String(64), nullable=False, unique=True)  # SHA256
    data_year = Column(Integer, index=True, nullable=False)  # DVF year (2023, 2024, etc.)

    # Import statistics
    total_records = Column(Integer)  # Total records in source file
    inserted_records = Column(Integer)  # New records added
    updated_records = Column(Integer)  # Existing records updated
    skipped_records = Column(Integer)  # Duplicate records skipped
    error_records = Column(Integer, default=0)  # Records that failed

    # Timing information
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)  # Null if still running
    duration_seconds = Column(Float)  # Total import time

    # Status tracking
    status = Column(String, nullable=False)  # 'running', 'completed', 'failed', 'rolled_back'
    error_message = Column(Text)  # Error details if status='failed'

    # Indexes for querying
    __table_args__ = (
        Index('idx_dvf_imports_status', 'status'),
        Index('idx_dvf_imports_year_status', 'data_year', 'status'),
    )
