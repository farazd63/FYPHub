"""Persisted scope and source metadata for the FYP group assistant."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from ..database import Base


class GroupAIDocumentChunk(Base):
    """A searchable, group-scoped slice of an authorized project record.

    The vector column uses the existing pgvector extension. The application
    keeps an offline, deterministic embedding fallback so indexing never sends
    private records to an unconfigured third-party service.
    """

    __tablename__ = "group_ai_document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "cycle_id",
            "group_id",
            "project_id",
            "document_id",
            "version_id",
            "section_name",
            "chunk_index",
            name="uq_group_ai_chunk_scope_source",
        ),
        CheckConstraint("chunk_index >= 0", name="ck_group_ai_chunk_index_nonnegative"),
        Index("ix_group_ai_chunks_scope", "cycle_id", "group_id", "project_id"),
        Index("ix_group_ai_chunks_source", "document_id", "version_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor_requests.id", ondelete="CASCADE"), nullable=True)
    document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version_id: Mapped[str] = mapped_column(String(128), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    section_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    document_status: Mapped[str] = mapped_column(String(32), nullable=False, default="AUTHORIZED", server_default="AUTHORIZED")
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class GroupAIResponse(Base):
    """Structured response metadata linked to an AI message."""

    __tablename__ = "group_ai_responses"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_group_ai_response_message"),
        Index("ix_group_ai_responses_scope", "cycle_id", "group_id", "project_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("group_messages.id", ondelete="CASCADE"), nullable=False)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor_requests.id", ondelete="CASCADE"), nullable=True)
    response_type: Mapped[str] = mapped_column(String(40), nullable=False, default="project", server_default="project")
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="low", server_default="low")
    sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    used_audit_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    used_version_comparison: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
