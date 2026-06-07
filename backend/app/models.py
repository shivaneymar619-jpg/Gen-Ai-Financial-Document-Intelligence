"""SQLAlchemy ORM models — maps the MVP spec's 11-table schema.

Soft deletes use `deleted_at`. Audit logs are append-only (no update/delete paths).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.orm import relationship

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    plan = Column(String, default="free")  # free | pro | enterprise
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)
    deleted_at = Column(DateTime, nullable=True)

    documents = relationship("Document", back_populates="owner")
    memberships = relationship("TeamMember", back_populates="user")


class Team(Base):
    __tablename__ = "teams"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=_now)
    deleted_at = Column(DateTime, nullable=True)

    members = relationship("TeamMember", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(String, primary_key=True, default=_uuid)
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String, default="member")  # owner | admin | member
    created_at = Column(DateTime, default=_now)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="memberships")


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    size_bytes = Column(Integer, default=0)
    pages = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending | processing | ready | failed
    error = Column(Text, nullable=True)
    storage_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)
    processed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """A text chunk + its embedding. This IS the persistent vector store
    (replaces the in-memory store that lost data on restart)."""
    __tablename__ = "document_chunks"
    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    page = Column(Integer, default=1)
    chunk_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # list[float] or null in keyword-fallback mode
    created_at = Column(DateTime, default=_now)

    document = relationship("Document", back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String, primary_key=True, default=_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, default="New chat")
    created_at = Column(DateTime, default=_now)
    deleted_at = Column(DateTime, nullable=True)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)  # [{document, page, snippet}]
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_now)

    session = relationship("ChatSession", back_populates="messages")


class AuditLog(Base):
    """Append-only compliance trail (SOX/GDPR)."""
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False, index=True)  # e.g. document.upload
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now, index=True)


class UsageMetric(Base):
    """Per-user usage for freemium enforcement + analytics."""
    __tablename__ = "usage_metrics"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    metric = Column(String, nullable=False)  # documents_uploaded | queries_made
    value = Column(Integer, default=0)
    period = Column(String, nullable=False)  # YYYY-MM
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, default="default")
    prefix = Column(String, index=True)       # shown to user
    hashed_key = Column(String, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    revoked = Column(Boolean, default=False)


class Template(Base):
    __tablename__ = "templates"
    id = Column(String, primary_key=True, default=_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    doc_type = Column(String, nullable=True)  # invoice | bank_statement | loan_agreement ...
    queries = Column(JSON, nullable=False)    # list[str]
    is_public = Column(Boolean, default=False)
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)


class BatchJob(Base):
    __tablename__ = "batch_jobs"
    id = Column(String, primary_key=True, default=_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    job_type = Column(String, default="ingest")  # ingest | batch_query
    status = Column(String, default="queued")     # queued | running | completed | failed
    total = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now)
    finished_at = Column(DateTime, nullable=True)
