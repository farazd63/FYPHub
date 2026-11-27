"""Supervisor profile evidence used by the administrator replacement workflow."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Float, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SupervisorProfile(Base):
    __tablename__ = "supervisor_profiles"
    __table_args__ = (
        CheckConstraint("profile_status IN ('DRAFT','PENDING_VERIFICATION','VERIFIED','REJECTED','ARCHIVED')", name="ck_supervisor_profiles_status"),
        CheckConstraint("visibility_status IN ('PRIVATE','PUBLIC')", name="ck_supervisor_profiles_visibility"),
        Index("ix_supervisor_profiles_status_visibility", "profile_status", "visibility_status"),
        Index("ix_supervisor_profiles_department_program", "department", "program"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    program: Mapped[str | None] = mapped_column(String(255), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_categories: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    publications: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    profile_status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT", server_default="DRAFT")
    visibility_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PRIVATE", server_default="PRIVATE")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    extracted_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SupervisorExpertise(Base):
    __tablename__ = "supervisor_expertise"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_supervisor_expertise_name"), Index("ix_supervisor_expertise_profile", "profile_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class SupervisorSkill(Base):
    __tablename__ = "supervisor_skills"
    __table_args__ = (UniqueConstraint("profile_id", "category", "name", name="uq_supervisor_skill_name"), Index("ix_supervisor_skills_profile", "profile_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="technical", server_default="technical")
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class SupervisorResearchInterest(Base):
    __tablename__ = "supervisor_research_interests"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_supervisor_research_interest_name"), Index("ix_supervisor_research_interests_profile", "profile_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class SupervisedProjectHistory(Base):
    __tablename__ = "supervised_project_history"
    __table_args__ = (Index("ix_supervised_project_history_profile", "profile_id"), Index("ix_supervised_project_history_cycle", "academic_cycle_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    project_title: Mapped[str] = mapped_column(String(255), nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_domain: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    problem_area: Mapped[str | None] = mapped_column(Text, nullable=True)
    methodology: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    academic_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("academic_cycles.id", ondelete="SET NULL"), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supervisor_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    project_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    public_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="DERIVED", server_default="DERIVED")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SupervisorAvailability(Base):
    __tablename__ = "supervisor_availability"
    __table_args__ = (UniqueConstraint("profile_id", "academic_cycle_id", name="uq_supervisor_availability_cycle"), Index("ix_supervisor_availability_cycle", "academic_cycle_id", "available"))

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("supervisor_profiles.id", ondelete="CASCADE"), nullable=False)
    academic_cycle_id: Mapped[int] = mapped_column(ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    maximum_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    current_active_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
