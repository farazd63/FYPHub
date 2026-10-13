"""User and role database foundation."""

from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from ..database import Base


class UserRole(str, Enum):
    STUDENT = "STUDENT"
    SUPERVISOR = "SUPERVISOR"
    COORDINATOR = "COORDINATOR"
    PANEL_MEMBER = "PANEL_MEMBER"
    ADMIN = "ADMIN"


class User(Base):
    """A future-authentication user record; password hashes only."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email = lower(btrim(email)) AND email <> ''",
            name="ck_users_email_normalized",
        ),
        CheckConstraint(
            "registration_number IS NULL OR "
            "(registration_number = upper(btrim(registration_number)) "
            "AND registration_number <> '')",
            name="ck_users_registration_number_normalized",
        ),
        CheckConstraint(
            "role != 'STUDENT' OR registration_number IS NOT NULL",
            name="ck_users_student_registration_required",
        ),
        Index("uq_users_email_normalized", text("lower(email)"), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role", native_enum=True, create_constraint=False),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @validates("email")
    def normalize_email(self, _: str, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("email must not be blank")
        return normalized

    @validates("registration_number")
    def normalize_registration_number(self, _: str, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None
