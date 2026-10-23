from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class MatchChat(Base):
    __tablename__ = "match_chats"
    __table_args__ = (CheckConstraint("team_a_id < team_b_id", name="ck_match_chats_team_order"), Index("uq_match_chats_open_pair", "team_a_id", "team_b_id", unique=True, postgresql_where=text("closed_at IS NULL")))
    id: Mapped[int] = mapped_column(primary_key=True)
    team_a_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    team_b_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class MatchMessage(Base):
    __tablename__ = "match_messages"
    __table_args__ = (Index("ix_match_messages_chat_id", "chat_id", "id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("match_chats.id", ondelete="RESTRICT"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class MatchConsent(Base):
    __tablename__ = "match_chat_consents"
    __table_args__ = (UniqueConstraint("closed_chat_id", "team_id", name="uq_match_chat_consent"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    closed_chat_id: Mapped[int] = mapped_column(ForeignKey("match_chats.id", ondelete="RESTRICT"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
