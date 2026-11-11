"""Schemas for public authentication-related endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from ..models import UserRole
from ..security import validate_full_name, validate_password
from .email import normalize_email


class RegistrationRequest(BaseModel):
    """Strict public registration input; privileged fields are forbidden."""

    model_config = ConfigDict(extra="forbid")

    full_name: str
    email: EmailStr
    registration_number: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalized_email(cls, value: object) -> object:
        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def normalized_name(cls, value: str) -> str:
        return validate_full_name(value)

    @field_validator("password")
    @classmethod
    def valid_password(cls, value: str) -> str:
        try:
            validate_password(value)
        except ValueError as error:
            raise ValueError(str(error)) from error
        return value


class RegistrationResponse(BaseModel):
    """Safe fields returned after a student account is registered."""

    id: int
    full_name: str
    email: str
    registration_number: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """Strict credentials accepted by the sign-in endpoint."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    registration_number: str | None = None
    password: str
    requested_role: UserRole | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalized_email(cls, value: object) -> object:
        return normalize_email(value)

    @model_validator(mode="after")
    def exactly_one_login_identifier(self) -> "LoginRequest":
        if (self.email is None) == (self.registration_number is None):
            raise ValueError("Provide exactly one of email or registration_number.")
        if self.registration_number is not None:
            normalized = self.registration_number.strip().upper()
            if not normalized or len(normalized) > 100:
                raise ValueError("registration_number must be between 1 and 100 characters.")
            self.registration_number = normalized
        return self


class CurrentUserResponse(BaseModel):
    """Safe account data returned after session authentication."""

    id: int
    full_name: str
    email: str
    registration_number: str | None
    role: UserRole
    is_active: bool
    group_id: int | None = None
    group_email: str | None = None
    principal_type: str = "ACCOUNT"
    group_name: str | None = None
    academic_cycle: str | None = None
    group_status: str | None = None
    members: list[dict[str, object]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
