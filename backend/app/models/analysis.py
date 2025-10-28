"""Analysis model for storing property analysis results."""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Analysis(Base):
    """Analysis model for comprehensive property evaluation."""

    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)

    # Overall scores
    investment_score = Column(Float)  # 0-100
    risk_score = Column(Float)  # 0-100
    value_score = Column(Float)  # 0-100
    overall_recommendation = Column(String)

    # Price analysis
    estimated_fair_price = Column(Float)
    price_deviation_percent = Column(Float)
    comparable_properties_count = Column(Integer)

    # Cost analysis
    annual_charges = Column(Float)
    annual_taxe_fonciere = Column(Float)
    upcoming_works_cost = Column(Float)
    estimated_annual_cost = Column(Float)

    # Risk factors
    has_amiante = Column(Boolean, default=False)
    has_plomb = Column(Boolean, default=False)
    dpe_rating = Column(String)  # A, B, C, D, E, F, G
    ges_rating = Column(String)  # Greenhouse gas rating

    # Copropriété analysis
    copropriete_health_score = Column(Float)  # 0-100
    pending_works = Column(Text)  # JSON array of upcoming works

    # Summary and recommendations
    summary = Column(Text)
    strengths = Column(Text)  # JSON array
    weaknesses = Column(Text)  # JSON array
    recommendations = Column(Text)  # JSON array

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="analyses")
