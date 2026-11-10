from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class GroupMessage(Base):
    __tablename__ = "group_messages"
    __table_args__ = (Index("ix_group_messages_team_channel_id", "team_id", "channel", "id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    author_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    thread_root_id: Mapped[int | None] = mapped_column(ForeignKey("group_messages.id", ondelete="SET NULL"), nullable=True)
    mentions: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    attachment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
