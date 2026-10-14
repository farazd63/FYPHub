"""Strict request and safe response schemas for shared-team registration."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from ..models import UserRole


class TeamMemberInput(BaseModel):
    """One creator or additional team contact record."""

    model_config = ConfigDict(extra="forbid")

    full_name: str
    registration_number: str
    university_email: EmailStr


class TeamRegistrationRequest(BaseModel):
    """Public input for one shared student login and its team contacts."""

    model_config = ConfigDict(extra="forbid")

    academic_cycle_id: int
    creator: TeamMemberInput
    shared_login_email: EmailStr
    password: str
    members: list[TeamMemberInput]


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
    university_email: str
    is_creator: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamRegistrationResponse(BaseModel):
    account: SafeAccountOut
    team: SafeTeamOut
    cycle: SafeCycleOut
    members: list[SafeTeamMemberOut]
