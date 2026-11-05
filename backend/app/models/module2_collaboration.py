"""Module 2 collaboration records: notifications, channel reads and moderation."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class Module2Notification(Base):
    __tablename__ = "module2_notifications"
    __table_args__ = (Index("ix_module2_notifications_recipient_created", "recipient_user_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Module2ChannelRead(Base):
    __tablename__ = "module2_channel_reads"
    __table_args__ = (UniqueConstraint("user_id", "team_id", "channel", name="uq_module2_channel_read"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    last_read_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Module2MatchReport(Base):
    __tablename__ = "module2_match_reports"
    __table_args__ = (CheckConstraint("status IN ('open','reviewed','dismissed')", name="ck_module2_match_report_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("match_chats.id", ondelete="CASCADE"), nullable=False)
    reporter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Module2ChatbotSession(Base):
    __tablename__ = "module2_chatbot_sessions"
    __table_args__ = (Index("ix_module2_chatbot_sessions_team_created", "team_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Group assistant", server_default="Group assistant")
    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
