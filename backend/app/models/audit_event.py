"""Append-only audit records for administrator account mutations."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AdminAuditEvent(Base):
    """A safe, immutable record of one successful administrator account mutation."""

    __tablename__ = "admin_audit_events"
    __table_args__ = (
        Index("ix_admin_audit_events_affected_user_id", "affected_user_id"),
        Index("ix_admin_audit_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    affected_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="USER")
    target_id: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
