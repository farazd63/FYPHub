from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class JoinRequest(Base):
    __tablename__ = 'join_requests'
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name='ck_join_request_status'),
        Index('uq_pending_join_request', 'team_id', 'student_id', unique=True, postgresql_where=text("status = 'pending'")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey('teams.id', ondelete='RESTRICT'), nullable=False)
    cycle_id: Mapped[int] = mapped_column(ForeignKey('academic_cycles.id', ondelete='RESTRICT'), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey('approved_students.id', ondelete='RESTRICT'), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending', server_default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class JoinRequestAudit(Base):
    __tablename__ = 'join_request_audit'
    __table_args__ = (CheckConstraint("action IN ('submitted', 'accepted', 'rejected')", name='ck_join_audit_action'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey('join_requests.id', ondelete='RESTRICT'), nullable=False)
    actor_student_id: Mapped[int] = mapped_column(ForeignKey('approved_students.id', ondelete='RESTRICT'), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
