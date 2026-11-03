from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

RequirementType = Literal["DEADLINE", "DOCUMENT", "APPROVAL", "TASK", "MILESTONE", "SUBMISSION"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Roles = Literal["STUDENT", "SUPERVISOR", "PANEL_MEMBER", "COORDINATOR", "ADMIN"]

class DashboardRequirementWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    academic_deadline_id: int | None = Field(default=None, gt=0)
    academic_cycle_id: int = Field(gt=0)
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    requirement_type: RequirementType
    module: str = Field(min_length=1, max_length=120)
    priority: Priority = "MEDIUM"
    role_visibility: list[Roles] = Field(min_length=1)
    assigned_user_id: int | None = Field(default=None, gt=0)
    assigned_group_id: int | None = Field(default=None, gt=0)
    due_at: datetime
    completion_percent: int = Field(default=0, ge=0, le=100)
    is_required: bool = True

    @field_validator("title", "module")
    @classmethod
    def trim_required(cls, value: str) -> str:
        value = value.strip()
        if not value: raise ValueError("Value must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

class DashboardRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; title: str; description: str | None; due_date: datetime; timezone: str
    academic_cycle: int; module: str; requirement_type: str; priority: str; status: str
    completion_percent: int; is_required: bool; source_deadline_id: int | None
    assigned_to_current_user: bool; can_update: bool

