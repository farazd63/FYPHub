"""API contracts for the institution control plane."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .email import normalize_email


class InstitutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=255)


class InstitutionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=255)
    status: str | None = Field(default=None, pattern="^(ACTIVE|DISABLED)$")


class InstitutionOut(BaseModel):
    id: int
    slug: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionDomainCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=3, max_length=255)

    @field_validator("domain")
    @classmethod
    def normalized_domain(cls, value: str) -> str:
        normalized = value.strip().lower().lstrip("@")
        if not normalized or "@" in normalized or " " in normalized or "." not in normalized:
            raise ValueError("Enter a valid email domain.")
        return normalized


class InstitutionDomainUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str | None = Field(default=None, min_length=3, max_length=255)
    is_active: bool | None = None
    is_verified: bool | None = None

    @field_validator("domain")
    @classmethod
    def normalized_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().lstrip("@")
        if not normalized or "@" in normalized or " " in normalized or "." not in normalized:
            raise ValueError("Enter a valid email domain.")
        return normalized


class InstitutionDomainOut(BaseModel):
    id: int
    institution_id: int
    domain: str
    is_verified: bool
    is_active: bool
    verified_at: datetime | None
    disabled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionInvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    expires_in_hours: int = Field(default=72, ge=1, le=720)

    @field_validator("email", mode="before")
    @classmethod
    def normalized_email(cls, value: object) -> object:
        return None if value in (None, "") else normalize_email(value)


class InstitutionInvitationOut(BaseModel):
    id: int
    institution_id: int
    email: str | None
    status: str
    expires_at: datetime
    created_at: datetime
    invitation_token: str | None = None

    model_config = ConfigDict(from_attributes=True)


class InstitutionMembershipOut(BaseModel):
    id: int
    institution_id: int
    user_id: int
    membership_role: str
    status: str
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=256)

