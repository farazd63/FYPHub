"""Schemas for public authentication-related endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, model_validator

from ..models import UserRole


class RegistrationRequest(BaseModel):
    """Strict public registration input; privileged fields are forbidden."""

    model_config = ConfigDict(extra="forbid")

    full_name: str
    email: EmailStr
    registration_number: str
    password: str


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

    model_config = ConfigDict(from_attributes=True)
