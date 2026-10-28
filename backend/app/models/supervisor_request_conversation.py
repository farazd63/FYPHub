"""Append-only messages scoped to one supervisor request."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SupervisorRequestMessage(Base):
    __tablename__ = "supervisor_request_messages"
    __table_args__ = (Index("ix_supervisor_request_messages_request_id", "request_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
