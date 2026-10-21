from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class WorkflowPolicy(Base):
    __tablename__ = "workflow_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class WorkflowPolicyVersion(Base):
    __tablename__ = "workflow_policy_versions"
    __table_args__ = (UniqueConstraint("policy_id", "version_number", name="uq_workflow_policy_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("workflow_policies.id", ondelete="RESTRICT"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    states: Mapped[list] = mapped_column(JSON, nullable=False)
    transitions: Mapped[list] = mapped_column(JSON, nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
