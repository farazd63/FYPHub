"""Logical FYP archive records and immutable document versions."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ArchivedProjectDocumentType(StrEnum):
    SHORT_PROPOSAL = "SHORT_PROPOSAL"
    LONG_PROPOSAL = "LONG_PROPOSAL"
    CHAPTER_1 = "CHAPTER_1"
    CHAPTER_2 = "CHAPTER_2"
    CHAPTER_3 = "CHAPTER_3"
    CHAPTER_4 = "CHAPTER_4"
    FINAL_REPORT = "FINAL_REPORT"
    FINAL_PACKAGE = "FINAL_PACKAGE"
    REFERENCES = "REFERENCES"
    OTHER = "OTHER"


class ArchivedProject(Base):
    __tablename__ = "archived_projects"
    __table_args__ = (
        Index("ix_archived_projects_normalized_title", "normalized_title"),
        Index("ix_archived_projects_active_cycle", "is_active", "academic_year"),
        Index("ix_archived_projects_active_scope", "is_active", "project_scope"),
        Index("uq_archived_project_active_title_year", "normalized_title", "academic_year", unique=True, postgresql_where=text("is_active = true")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(255), nullable=False)
    abstract_summary: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False, default=list, server_default="{}")
    academic_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=True)
    academic_year: Mapped[str] = mapped_column(String(64), nullable=False)
    department_program: Mapped[str] = mapped_column(String(255), nullable=False)
    project_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    completion_stage: Mapped[str] = mapped_column(String(100), nullable=False)
    implemented_scope: Mapped[str] = mapped_column(Text, nullable=False)
    remaining_gaps: Mapped[str] = mapped_column(Text, nullable=False)
    future_work: Mapped[str] = mapped_column(Text, nullable=False)
    supervisor_display_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_label: Mapped[str] = mapped_column(String(64), nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ArchivedProjectDocument(Base):
    __tablename__ = "archived_project_documents"
    __table_args__ = (
        Index("ix_archived_project_documents_project_type", "archived_project_id", "document_type", "version"),
        Index("uq_archived_project_active_document_type", "archived_project_id", "document_type", unique=True, postgresql_where=text("is_active = true")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    archived_project_id: Mapped[int] = mapped_column(ForeignKey("archived_projects.id", ondelete="RESTRICT"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
