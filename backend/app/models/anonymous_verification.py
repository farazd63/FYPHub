"""Anonymous browser verification persistence, independent of user sessions."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class AnonymousVerificationContext(Base):
    __tablename__ = 'anonymous_verification_contexts'
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    client_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class AnonymousVerificationChallenge(Base):
    __tablename__ = 'anonymous_verification_challenges'
    __table_args__ = (CheckConstraint("purpose IN ('join_request', 'invitation', 'student_matching')", name='ck_anon_challenge_purpose'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    context_id: Mapped[int] = mapped_column(ForeignKey('anonymous_verification_contexts.id', ondelete='RESTRICT'), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey('approved_students.id', ondelete='RESTRICT'), nullable=False, index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey('academic_cycles.id', ondelete='RESTRICT'), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str | None] = mapped_column(String(32))
    target_team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id', ondelete='RESTRICT'))
    target_invitation_id: Mapped[int | None] = mapped_column(ForeignKey('team_invitations.id', ondelete='RESTRICT'))
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class AnonymousIdentityProof(Base):
    __tablename__ = 'anonymous_identity_proofs'
    __table_args__ = (CheckConstraint("purpose IN ('join_request', 'invitation', 'student_matching')", name='ck_anon_proof_purpose'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey('anonymous_verification_challenges.id', ondelete='RESTRICT'), unique=True, nullable=False)
    context_id: Mapped[int] = mapped_column(ForeignKey('anonymous_verification_contexts.id', ondelete='RESTRICT'), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey('approved_students.id', ondelete='RESTRICT'), nullable=False)
    cycle_id: Mapped[int] = mapped_column(ForeignKey('academic_cycles.id', ondelete='RESTRICT'), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str | None] = mapped_column(String(32))
    target_team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id', ondelete='RESTRICT'))
    target_invitation_id: Mapped[int | None] = mapped_column(ForeignKey('team_invitations.id', ondelete='RESTRICT'))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
