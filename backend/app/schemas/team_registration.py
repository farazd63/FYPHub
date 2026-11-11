"""Strict request and safe response schemas for shared-team registration."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from ..models import UserRole
from ..security import validate_full_name
from .email import normalize_email


class TeamMemberInput(BaseModel):
    """One group leader or colleague record; contact email is legacy-only."""

    model_config = ConfigDict(extra="forbid")

    full_name: str
    registration_number: str
    university_email: EmailStr | None = None

    @field_validator("university_email", mode="before")
    @classmethod
    def normalized_email(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return normalize_email(value)


class TeamRegistrationRequest(BaseModel):
    """Public input for one shared student login and its team contacts."""

    model_config = ConfigDict(extra="forbid")

    academic_cycle_id: int
    creator: TeamMemberInput
    shared_login_email: EmailStr
    password: str
    confirm_password: str | None = None
    members: list[TeamMemberInput]

    @field_validator("shared_login_email", mode="before")
    @classmethod
    def normalized_shared_email(cls, value: object) -> object:
        return normalize_email(value)


class SafeAccountOut(BaseModel):
    id: int
    full_name: str
    email: str
    registration_number: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SafeTeamOut(BaseModel):
    id: int
    academic_cycle_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SafeCycleOut(BaseModel):
    id: int
    code: str
    display_name: str

    model_config = ConfigDict(from_attributes=True)


class SafeTeamMemberOut(BaseModel):
    id: int
    full_name: str
    registration_number: str
    university_email: str | None
    is_creator: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamRegistrationResponse(BaseModel):
    account: SafeAccountOut
    team: SafeTeamOut
    cycle: SafeCycleOut
    members: list[SafeTeamMemberOut]


class StudentGroupMemberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    registration_number: str
    full_name: str
    designation: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalized_member_email(cls, value: object) -> object:
        return normalize_email(value)

    @field_validator("registration_number")
    @classmethod
    def normalized_registration(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized or len(normalized) > 100:
            raise ValueError("registration_number must be between 1 and 100 characters.")
        return normalized

    @field_validator("full_name")
    @classmethod
    def normalized_name(cls, value: str) -> str:
        return validate_full_name(value)


class StudentGroupRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    academic_cycle_id: int
    group_name: str | None = None
    group_email: EmailStr
    password: str
    confirm_password: str
    members: list[StudentGroupMemberInput]

    @field_validator("group_email", mode="before")
    @classmethod
    def normalized_group_email(cls, value: object) -> object:
        return normalize_email(value)

    @field_validator("group_name")
    @classmethod
    def normalized_group_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized or len(normalized) > 255:
            raise ValueError("group_name must be between 1 and 255 characters.")
        return normalized
