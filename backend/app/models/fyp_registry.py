"""Administrative metadata layered over immutable student proposal records."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class FypRegistryMetadata(Base):
    __tablename__ = "fyp_registry_metadata"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_fyp_registry_metadata_request"),
        Index("ix_fyp_registry_metadata_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=False)
    department_section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    administrative_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
