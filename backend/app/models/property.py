"""Property and DVF record models."""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, Text
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

    created_at = Column(DateTime, default=datetime.utcnow)
