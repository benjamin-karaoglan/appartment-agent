"""Document model for uploaded files."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Document(Base):
    """Document model for storing uploaded files and their analysis."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)

    # Document information
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String)  # pdf, image, etc.
    document_category = Column(String)  # pv_ag, diags, taxe_fonciere, charges, photo
    document_subcategory = Column(String)  # For diags: dpe, amiante, plomb, termite, electric, gas

    # Document date (e.g., meeting date for PV, diagnostic date)
    document_date = Column(DateTime, nullable=True)

    # Analysis results
    is_analyzed = Column(Boolean, default=False)
    analysis_summary = Column(Text)
    extracted_data = Column(Text)  # JSON string of extracted data
    risk_flags = Column(Text)  # JSON array of identified risks

    # Enhanced structured data
    key_insights = Column(JSON, nullable=True)  # Array of important points

    # Cost estimates extracted from document
    estimated_annual_cost = Column(Float, nullable=True)
    one_time_costs = Column(JSON, nullable=True)  # List of one-time costs with amounts

    # Metadata
    upload_date = Column(DateTime, default=datetime.utcnow)
    parsed_at = Column(DateTime, nullable=True)
    file_size = Column(Integer)  # in bytes

    # Relationships
    user = relationship("User", back_populates="documents")
    property = relationship("Property", back_populates="documents")


class DocumentSummary(Base):
    """Aggregated summaries for groups of documents (e.g., all PV d'AG for a property)"""
    __tablename__ = "document_summaries"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    category = Column(String, nullable=False)  # pv_ag, diags, taxe_fonciere, charges

    # Aggregated analysis
    summary = Column(Text, nullable=True)
    key_findings = Column(JSON, nullable=True)

    # Financial summary
    total_estimated_annual_cost = Column(Float, nullable=True)
    total_one_time_costs = Column(Float, nullable=True)
    cost_breakdown = Column(JSON, nullable=True)

    # Specific insights per category
    # For PV d'AG: copropriétaire behavior, upcoming works, payment issues
    copropriete_insights = Column(JSON, nullable=True)

    # For Diags: urgent issues, compliance status
    diagnostic_issues = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_document_count = Column(Integer, default=0)  # Track when summary needs updating

    # Relationship
    property = relationship("Property")
