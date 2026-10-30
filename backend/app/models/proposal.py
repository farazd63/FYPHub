"""Non-operational identity and version foundations for proposals."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (CheckConstraint("proposal_type IN ('SHORT', 'LONG')", name="ck_proposals_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(5), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProposalVersion(Base):
    __tablename__ = "proposal_versions"
    __table_args__ = (
        UniqueConstraint("proposal_id", "version_number", name="uq_proposal_version_number"),
        CheckConstraint("version_number > 0", name="ck_proposal_version_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id", ondelete="RESTRICT"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
