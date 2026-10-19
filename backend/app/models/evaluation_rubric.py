"""Draft evaluation-rubric configuration models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class EvaluationRubric(Base):
    """Stable identity shared by every immutable draft version."""

    __tablename__ = "evaluation_rubrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    versions: Mapped[list["EvaluationRubricVersion"]] = relationship(back_populates="rubric")


class EvaluationRubricVersion(Base):
    """A complete immutable snapshot of one draft rubric."""

    __tablename__ = "evaluation_rubric_versions"
    __table_args__ = (
        UniqueConstraint("rubric_id", "version_number", name="uq_evaluation_rubric_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rubric_id: Mapped[int] = mapped_column(ForeignKey("evaluation_rubrics.id", ondelete="RESTRICT"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    rubric: Mapped[EvaluationRubric] = relationship(back_populates="versions")
    criteria: Mapped[list["EvaluationRubricCriterion"]] = relationship(back_populates="rubric_version")


class EvaluationRubricCriterion(Base):
    """An ordered criterion belonging exclusively to one rubric version."""

    __tablename__ = "evaluation_rubric_criteria"
    __table_args__ = (
        UniqueConstraint("rubric_version_id", "display_order", name="uq_evaluation_rubric_criterion_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rubric_version_id: Mapped[int] = mapped_column(ForeignKey("evaluation_rubric_versions.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    rubric_version: Mapped[EvaluationRubricVersion] = relationship(back_populates="criteria")
