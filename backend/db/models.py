from __future__ import annotations

from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = {"schema": "profile"}

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_json = Column(JSONB, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
    )


class AlumniRecord(Base):
    __tablename__ = "alumni_records"
    __table_args__ = {"schema": "kb"}

    alumni_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_doc = Column(String(500))
    record_json = Column(JSONB, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    tags = Column(ARRAY(String))
    created_at = Column(DateTime(timezone=True), default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "chat"}

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    messages = Column(JSONB, nullable=False, default=list)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
