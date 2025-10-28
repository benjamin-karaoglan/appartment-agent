"""Document model for uploaded files."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
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
    document_category = Column(String)  # PV_AG, diagnostic, tax, charges, photo

    # Analysis results
    is_analyzed = Column(Boolean, default=False)
    analysis_summary = Column(Text)
    extracted_data = Column(Text)  # JSON string of extracted data
    risk_flags = Column(Text)  # JSON array of identified risks

    # Metadata
    upload_date = Column(DateTime, default=datetime.utcnow)
    file_size = Column(Integer)  # in bytes

    # Relationships
    user = relationship("User", back_populates="documents")
    property = relationship("Property", back_populates="documents")
