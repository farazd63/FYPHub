"""Module 2 collaboration records: notifications, channel reads and moderation."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func, text
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


class Module2ChatbotSession(Base):
    __tablename__ = "module2_chatbot_sessions"
    __table_args__ = (Index("ix_module2_chatbot_sessions_team_created", "team_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Group assistant", server_default="Group assistant")
    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CollaborationChannel(Base):
    __tablename__ = "collaboration_channels"
    __table_args__ = (
        Index("uq_collaboration_channel_active_assignment", "team_id", "supervisor_id", "assignment_id", unique=True, postgresql_where=text("status = 'ACTIVE'")),
        Index("ix_collaboration_channels_supervisor_status", "supervisor_id", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    session: Mapped[str] = mapped_column(String(16), nullable=False)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("supervisor_assignments.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CollaborationParticipant(Base):
    __tablename__ = "collaboration_participants"
    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_collaboration_participant_user"),
        Index("ix_collaboration_participants_channel_active", "channel_id", "is_active"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("collaboration_channels.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    team_member_id: Mapped[int | None] = mapped_column(ForeignKey("team_members.id", ondelete="CASCADE"), nullable=True)
    participant_role: Mapped[str] = mapped_column(String(24), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class CollaborationMessage(Base):
    __tablename__ = "collaboration_messages"
    __table_args__ = (Index("ix_collaboration_messages_channel_created", "channel_id", "created_at", "id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("collaboration_channels.id", ondelete="RESTRICT"), nullable=False)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
