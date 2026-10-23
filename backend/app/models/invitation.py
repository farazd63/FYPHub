"""Invitation records and student-attributed append-only history."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class Invitation(Base):
    __tablename__ = 'team_invitations'
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name='ck_team_invitation_status'),
        Index('uq_pending_team_invitation', 'team_id', 'student_id', unique=True, postgresql_where=text("status = 'pending'")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey('teams.id', ondelete='RESTRICT'), nullable=False)
    cycle_id: Mapped[int] = mapped_column(ForeignKey('academic_cycles.id', ondelete='RESTRICT'), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey('approved_students.id', ondelete='RESTRICT'), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class InvitationAudit(Base):
    __tablename__ = 'team_invitation_audit'
    __table_args__ = (CheckConstraint("action IN ('sent', 'queued', 'accepted', 'rejected')", name='ck_invitation_audit_action'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    invitation_id: Mapped[int] = mapped_column(ForeignKey('team_invitations.id', ondelete='RESTRICT'), nullable=False)
    actor_student_id: Mapped[int] = mapped_column(ForeignKey('approved_students.id', ondelete='RESTRICT'), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class InvitationOutbox(Base):
    __tablename__ = 'invitation_outbox'
    __table_args__ = (CheckConstraint("status IN ('queued', 'smtp_accepted', 'failed', 'unknown')", name='ck_invitation_outbox_status'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    invitation_id: Mapped[int] = mapped_column(ForeignKey('team_invitations.id', ondelete='RESTRICT'), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default='queued', default='queued')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
