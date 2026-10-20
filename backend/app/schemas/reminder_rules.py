"""Strict configuration-only rule requests."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class RulePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deadline_version_id: int = Field(gt=0, strict=True)
    direction: Literal["BEFORE", "AFTER"]
    elapsed_minutes: int = Field(gt=0, le=2147483647, strict=True)

class RuleWrite(RulePreview):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    category: Literal["REMINDER", "ESCALATION"]
    @field_validator("name")
    @classmethod
    def name_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value

class RuleCreate(RuleWrite):
    academic_cycle_id: int = Field(gt=0, strict=True)
