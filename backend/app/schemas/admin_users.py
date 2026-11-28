"""Strict, safe contracts for ADMIN-only account management."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from ..models import UserRole
from ..security import validate_full_name, validate_password
from .email import normalize_email


class AdminUserResponse(BaseModel):
    id: int
    full_name: str
    group_name: str | None = None
    email: str
    registration_number: str | None
    role: UserRole
    roles: list[UserRole] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    coordinator_academic_cycle_ids: list[int] = Field(default_factory=list)
    coordinator_academic_cycle_names: list[str] = Field(default_factory=list)
    # Kept for clients that still read the former single-cycle response fields.
    coordinator_academic_cycle_id: int | None = None
    coordinator_academic_cycle_name: str | None = None
    verification_token: str | None = None

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
    role: UserRole | None = None
    roles: list[UserRole] = Field(default_factory=list)
    registration_number: str | None = None
    coordinator_academic_cycle_ids: list[int] = Field(default_factory=list)
    # Backward-compatible input for older clients; it is folded into the list.
    coordinator_academic_cycle_id: int | None = None

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
        selected_roles = list(dict.fromkeys(self.roles))
        if self.role is not None and self.role not in selected_roles:
            selected_roles.insert(0, self.role)
        if not selected_roles:
            raise ValueError("Select at least one account role.")
        self.roles = selected_roles
        self.role = selected_roles[0]
        cycle_ids = list(dict.fromkeys(self.coordinator_academic_cycle_ids))
        if self.coordinator_academic_cycle_id is not None and self.coordinator_academic_cycle_id not in cycle_ids:
            cycle_ids.append(self.coordinator_academic_cycle_id)
        self.coordinator_academic_cycle_ids = cycle_ids
        if UserRole.STUDENT in selected_roles and len(selected_roles) > 1:
            raise ValueError("STUDENT accounts cannot have additional roles.")
        if self.role == UserRole.STUDENT and self.registration_number is None:
            raise ValueError("registration_number is required for STUDENT accounts.")
        if UserRole.COORDINATOR in selected_roles and not cycle_ids:
            raise ValueError("coordinator_academic_cycle_ids is required for COORDINATOR accounts.")
        if UserRole.COORDINATOR not in selected_roles and cycle_ids:
            raise ValueError("Coordinator cycles require the COORDINATOR role.")
        return self


class AdminUserUpdate(BaseModel):
    """Editable account metadata; credentials are managed separately."""

    model_config = ConfigDict(extra="forbid")

    full_name: str
    email: EmailStr
    registration_number: str | None = None
    role: UserRole | None = None
    roles: list[UserRole] = Field(default_factory=list)
    coordinator_academic_cycle_ids: list[int] = Field(default_factory=list)
    # Backward-compatible input for older clients; it is folded into the list.
    coordinator_academic_cycle_id: int | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalized_email(cls, value: object) -> object:
        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return validate_full_name(value)

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
    def student_has_registration(self) -> "AdminUserUpdate":
        selected_roles = list(dict.fromkeys(self.roles))
        if self.role is not None and self.role not in selected_roles:
            selected_roles.insert(0, self.role)
        if not selected_roles:
            raise ValueError("Select at least one account role.")
        self.roles = selected_roles
        self.role = selected_roles[0]
        cycle_ids = list(dict.fromkeys(self.coordinator_academic_cycle_ids))
        if self.coordinator_academic_cycle_id is not None and self.coordinator_academic_cycle_id not in cycle_ids:
            cycle_ids.append(self.coordinator_academic_cycle_id)
        self.coordinator_academic_cycle_ids = cycle_ids
        if UserRole.STUDENT in selected_roles and len(selected_roles) > 1:
            raise ValueError("STUDENT accounts cannot have additional roles.")
        if self.role == UserRole.STUDENT and self.registration_number is None:
            raise ValueError("registration_number is required for STUDENT accounts.")
        if UserRole.COORDINATOR in selected_roles and not cycle_ids:
            raise ValueError("coordinator_academic_cycle_ids is required for COORDINATOR accounts.")
        if UserRole.COORDINATOR not in selected_roles and cycle_ids:
            raise ValueError("Coordinator cycles require the COORDINATOR role.")
        return self


class AdminUserRoleChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: UserRole | None = None
    roles: list[UserRole] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_roles(self) -> "AdminUserRoleChange":
        selected_roles = list(dict.fromkeys(self.roles))
        if self.role is not None and self.role not in selected_roles:
            selected_roles.insert(0, self.role)
        if not selected_roles:
            raise ValueError("Select at least one account role.")
        if UserRole.STUDENT in selected_roles and len(selected_roles) > 1:
            raise ValueError("STUDENT accounts cannot have additional roles.")
        self.roles = selected_roles
        self.role = selected_roles[0]
        return self


class AdminUserStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


class AdminUserPasswordChange(BaseModel):
    """A replacement password; existing credentials are never readable."""

    model_config = ConfigDict(extra="forbid")

    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def valid_password(cls, value: str) -> str:
        try:
            validate_password(value)
        except ValueError as error:
            raise ValueError(str(error)) from error
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> "AdminUserPasswordChange":
        if self.new_password != self.confirm_password:
            raise ValueError("Password and confirmation password must match.")
        return self


class AdminStudentGroupMemberCreate(BaseModel):
    """Member identity data added to an existing group portal account."""

    model_config = ConfigDict(extra="forbid")

    full_name: str
    email: EmailStr
    registration_number: str

    @field_validator("email", mode="before")
    @classmethod
    def normalized_email(cls, value: object) -> object:
        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return validate_full_name(value)

    @field_validator("registration_number")
    @classmethod
    def normalized_registration(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized or len(normalized) > 100:
            raise ValueError("registration_number must be between 1 and 100 characters.")
        return normalized


class AdminStudentGroupMemberUpdate(AdminStudentGroupMemberCreate):
    """Editable identity fields for an active member of an admin-managed group."""

    designation: Literal["LEADER", "MEMBER"] | None = None


class AdminStudentGroupApproval(BaseModel):
    """Optional compatibility payload for automatic group-name assignment."""

    model_config = ConfigDict(extra="forbid")

    group_name: str | None = None

    @field_validator("group_name")
    @classmethod
    def normalized_group_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized or len(normalized) > 255:
            raise ValueError("group_name must be between 1 and 255 characters.")
        return normalized

