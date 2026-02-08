"""
Photo model for apartment redesign feature.
"""

import uuid as uuid_lib
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Photo(Base):
    """Model for uploaded apartment photos."""

    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        String(36), unique=True, index=True, nullable=True, default=lambda: str(uuid_lib.uuid4())
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)

    # Original photo
    filename = Column(String, nullable=False)
    storage_key = Column(String, nullable=False)
    storage_bucket = Column(String, default="photos")
    file_size = Column(Integer)
    mime_type = Column(String)

    # Metadata
    room_type = Column(String, nullable=True)  # living_room, bedroom, kitchen, etc.
    description = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Promoted redesign for property overview
    promoted_redesign_id = Column(Integer, ForeignKey("photo_redesigns.id"), nullable=True)

    # Relationships
    redesigns = relationship(
        "PhotoRedesign",
        back_populates="original_photo",
        cascade="all, delete-orphan",
        foreign_keys="[PhotoRedesign.photo_id]",
    )
    promoted_redesign = relationship(
        "PhotoRedesign", uselist=False, foreign_keys=[promoted_redesign_id]
    )

    def __repr__(self):
        return f"<Photo {self.id}: {self.filename}>"


class PhotoRedesign(Base):
    """Model for AI-generated apartment redesigns."""

    __tablename__ = "photo_redesigns"

    id = Column(Integer, primary_key=True, index=True)
    redesign_uuid = Column(
        String, unique=True, index=True, nullable=False, default=lambda: str(uuid_lib.uuid4())
    )
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)

    # Generated image
    storage_key = Column(String, nullable=False)
    storage_bucket = Column(String, default="photos")
    file_size = Column(Integer)

    # Generation parameters
    style_preset = Column(String, nullable=True)  # modern_norwegian, minimalist_scandinavian, etc.
    prompt = Column(Text, nullable=False)
    aspect_ratio = Column(String, default="16:9")
    model_used = Column(String, default="gemini-2.5-flash-image")

    # Conversation history for multi-turn
    conversation_history = Column(JSON, nullable=True)
    is_multi_turn = Column(Boolean, default=False)
    parent_redesign_id = Column(Integer, ForeignKey("photo_redesigns.id"), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    generation_time_ms = Column(Integer, nullable=True)

    # User feedback
    is_favorite = Column(Boolean, default=False)
    user_rating = Column(Integer, nullable=True)  # 1-5 stars

    # Relationships
    original_photo = relationship("Photo", back_populates="redesigns", foreign_keys=[photo_id])
    parent_redesign = relationship("PhotoRedesign", remote_side=[id], backref="iterations")

    def __repr__(self):
        return f"<PhotoRedesign {self.id}: {self.style_preset or 'custom'}>"
