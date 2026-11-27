"""Request contracts for the centralized announcement system."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Priority = Literal["NORMAL", "IMPORTANT", "URGENT"]
TargetType = Literal["ALL_USERS", "ALL_GROUPS", "ROLE", "CYCLE", "GROUP", "PROJECT", "ASSIGNED_STUDENTS", "ASSIGNED_PANEL"]


class AnnouncementWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=20000)
    priority: Priority = "NORMAL"
    target_type: TargetType
    target_role: str | None = Field(default=None, max_length=32)
    cycle_id: int | None = Field(default=None, gt=0)
    group_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
    published_at: datetime | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_and_validate_scope(self):
        self.title = self.title.strip()
        self.message = self.message.strip()
        if self.published_at is not None and self.published_at.tzinfo is None:
            self.published_at = self.published_at.replace(tzinfo=timezone.utc)
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            self.expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        if not self.title or not self.message:
            raise ValueError("title and message must not be blank")
        if self.expires_at is not None and self.published_at is not None and self.expires_at <= self.published_at:
            raise ValueError("expires_at must be later than published_at")
        if self.target_type == "ROLE" and not self.target_role:
            raise ValueError("target_role is required for role announcements")
        if self.target_type == "CYCLE" and self.cycle_id is None:
            raise ValueError("cycle_id is required for cycle announcements")
        if self.target_type == "GROUP" and self.group_id is None:
            raise ValueError("group_id is required for group announcements")
        if self.target_type == "PROJECT" and self.project_id is None:
            raise ValueError("project_id is required for project announcements")
        if self.target_type in {"ALL_USERS", "ALL_GROUPS", "ROLE", "CYCLE", "GROUP", "PROJECT", "ASSIGNED_STUDENTS", "ASSIGNED_PANEL"}:
            return self
        return self


class AnnouncementPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    message: str | None = Field(default=None, min_length=1, max_length=20000)
    priority: Priority | None = None
    target_type: TargetType | None = None
    target_role: str | None = Field(default=None, max_length=32)
    cycle_id: int | None = Field(default=None, gt=0)
    group_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
    published_at: datetime | None = None
    expires_at: datetime | None = None


class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    author_id: int
    author_name: str
    author_role: str
    priority: str
    status: str
    target_type: str
    target_role: str | None
    cycle_id: int | None
    group_id: int | None
    project_id: int | None
    group_number: int | None = None
    group_name: str | None = None
    published_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    read_at: datetime | None = None
    is_read: bool = False
    can_edit: bool = False
    can_archive: bool = False


class AnnouncementScopeOption(BaseModel):
    id: int
    label: str
    cycle_id: int | None = None
    group_id: int | None = None
    project_id: int | None = None


class AnnouncementPermissions(BaseModel):
    can_create: bool
    can_manage: bool
    allowed_target_types: list[str]
    allowed_roles: list[str]
    cycles: list[AnnouncementScopeOption] = Field(default_factory=list)
    groups: list[AnnouncementScopeOption] = Field(default_factory=list)
    projects: list[AnnouncementScopeOption] = Field(default_factory=list)
