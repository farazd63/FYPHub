"""Cross-tenant institution control-plane records."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from ..database import ControlPlaneBase


class Institution(ControlPlaneBase):
    __tablename__ = "institutions"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','DISABLED')", name="ck_institutions_status"),
        Index("uq_institutions_slug_normalized", text("lower(slug)"), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    @validates("slug")
    def normalize_slug(self, _key: str, value: str) -> str:
        normalized = "-".join(value.strip().lower().split())
        if not normalized:
            raise ValueError("institution slug must not be blank")
        return normalized

    @validates("name")
    def normalize_name(self, _key: str, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("institution name must not be blank")
        return normalized


class InstitutionDomain(ControlPlaneBase):
    __tablename__ = "institution_domains"
    __table_args__ = (
        CheckConstraint("domain = lower(btrim(domain)) AND domain <> ''", name="ck_institution_domains_normalized"),
        UniqueConstraint("institution_id", "domain", name="uq_institution_domains_institution_domain"),
        Index("uq_institution_domains_domain", "domain", unique=True),
        Index("ix_institution_domains_lookup", "domain", "is_verified", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    @validates("domain")
    def normalize_domain(self, _key: str, value: str) -> str:
        normalized = value.strip().lower().lstrip("@")
        if not normalized or "@" in normalized or " " in normalized:
            raise ValueError("domain must be a normalized host name")
        return normalized


class InstitutionMembership(ControlPlaneBase):
    __tablename__ = "institution_memberships"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','INVITED','APPROVED','ACTIVE','DISABLED','REJECTED')", name="ck_institution_memberships_status"),
        CheckConstraint("membership_role IN ('MEMBER','INSTITUTION_ADMIN')", name="ck_institution_memberships_role"),
        UniqueConstraint("institution_id", "user_id", name="uq_institution_memberships_institution_user"),
        Index("ix_institution_memberships_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    membership_role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="MEMBER")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    invited_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InstitutionInvitation(ControlPlaneBase):
    __tablename__ = "institution_invitations"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','ACCEPTED','EXPIRED','REVOKED')", name="ck_institution_invitations_status"),
        Index("ix_institution_invitations_email_status", "email", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    invited_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    @validates("email")
    def normalize_email(self, _key: str, value: str | None) -> str | None:
        return value.strip().lower() if value else None


class EmailVerificationToken(ControlPlaneBase):
    __tablename__ = "email_verification_tokens"
    __table_args__ = (Index("ix_email_verification_tokens_user_status", "user_id", "verified_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

