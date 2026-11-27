"""Metadata registry for documents used by the active knowledge workflow."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_knowledge_documents_source"),
        Index("ix_knowledge_documents_scope", "academic_cycle_id", "team_id", "supervisor_id"),
        Index("ix_knowledge_documents_permissions", "student_user_id", "supervisor_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    academic_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("academic_cycles.id", ondelete="SET NULL"), nullable=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    student_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    project_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    access_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
