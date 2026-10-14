"""Schemas for public authentication-related endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

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
