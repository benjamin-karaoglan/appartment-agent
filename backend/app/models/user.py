"""User model."""

import uuid as uuid_lib
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from app.core.database import Base

# Register ba_user table in SQLAlchemy metadata (managed by Better Auth via Next.js).
# This allows the ForeignKey on users.ba_user_id to resolve without a full ORM model.
Table(
    "ba_user",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    extend_existing=True,
)


class User(Base):
    """User model for authentication and profile management."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        String(36), unique=True, index=True, nullable=True, default=lambda: str(uuid_lib.uuid4())
    )
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    documents_analyzed_count = Column(Integer, default=0)
    redesigns_generated_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Better Auth integration - links to ba_user table
    ba_user_id = Column(
        String(36), ForeignKey("ba_user.id", ondelete="SET NULL"), unique=True, nullable=True
    )

    # Relationships
    properties = relationship("Property", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
