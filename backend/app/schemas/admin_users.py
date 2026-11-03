"""Strict, safe contracts for ADMIN-only account management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from ..models import UserRole
from ..security import validate_full_name, validate_password
from .email import normalize_email


class AdminUserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    registration_number: str | None
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserPage(BaseModel):
    items: list[AdminUserResponse]
    page: int
    page_size: int
    total: int


class AdminUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str
    email: EmailStr
    password: str
    role: UserRole
    registration_number: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalized_email(cls, value: object) -> object:
        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return validate_full_name(value)

    @field_validator("password")
    @classmethod
    def valid_password(cls, value: str) -> str:
        try:
            validate_password(value)
        except ValueError as error:
            raise ValueError(str(error)) from error
        return value

    @field_validator("registration_number")
    @classmethod
    def normalized_registration(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized or len(normalized) > 100:
            raise ValueError("registration_number must be between 1 and 100 characters.")
        return normalized

    @model_validator(mode="after")
    def student_has_registration(self) -> "AdminUserCreate":
        if self.role == UserRole.STUDENT and self.registration_number is None:
            raise ValueError("registration_number is required for STUDENT accounts.")
        return self


class AdminUserRoleChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: UserRole


class AdminUserStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool
