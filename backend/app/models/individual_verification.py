"""Roster-bound one-time identity verification storage."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class IdentityChallenge(Base):
    __tablename__ = "identity_challenges"
    __table_args__ = (CheckConstraint("purpose IN ('join_request', 'invitation')", name="ck_identity_challenge_purpose"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("approved_students.id", ondelete="RESTRICT"), nullable=False, index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str | None] = mapped_column(String(32))
    target_request_id: Mapped[int | None] = mapped_column(ForeignKey('join_requests.id', ondelete='RESTRICT'))
    target_team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id', ondelete='RESTRICT'))
    target_student_id: Mapped[int | None] = mapped_column(ForeignKey('approved_students.id', ondelete='RESTRICT'))
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class IdentityProof(Base):
    __tablename__ = "identity_proofs"
    __table_args__ = (CheckConstraint("purpose IN ('join_request', 'invitation')", name="ck_identity_proof_purpose"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("identity_challenges.id", ondelete="RESTRICT"), nullable=False, unique=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("approved_students.id", ondelete="RESTRICT"), nullable=False)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str | None] = mapped_column(String(32))
    target_request_id: Mapped[int | None] = mapped_column(ForeignKey('join_requests.id', ondelete='RESTRICT'))
    target_team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id', ondelete='RESTRICT'))
    target_student_id: Mapped[int | None] = mapped_column(ForeignKey('approved_students.id', ondelete='RESTRICT'))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
