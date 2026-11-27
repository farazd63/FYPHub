"""Non-operational identity and version foundations for proposals."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (CheckConstraint("proposal_type IN ('SHORT', 'LONG')", name="ck_proposals_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(5), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
