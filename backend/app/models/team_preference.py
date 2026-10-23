from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class TeamPreference(Base):
    __tablename__ = "team_match_preferences"
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), primary_key=True)
    opted_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
