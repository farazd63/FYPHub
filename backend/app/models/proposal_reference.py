"""Authorized archived proposal references and separate PDF documents."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ProposalReference(Base):
    __tablename__ = "proposal_references"
    __table_args__ = (
        Index("ix_proposal_references_normalized_title", "normalized_title"),
        Index("ix_proposal_references_cycle_active", "academic_cycle_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_summary: Mapped[str] = mapped_column(Text, nullable=False)
    academic_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=True)
    academic_year: Mapped[str] = mapped_column(String(32), nullable=False)
    category_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    source_label: Mapped[str] = mapped_column(String(64), nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProposalReferenceDocument(Base):
    __tablename__ = "proposal_reference_documents"
    __table_args__ = (Index("uq_proposal_reference_document_reference", "reference_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[int] = mapped_column(ForeignKey("proposal_references.id", ondelete="RESTRICT"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
