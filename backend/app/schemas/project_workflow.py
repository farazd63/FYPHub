"""Validated request payloads for project progress, defense, and evaluation APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MilestoneWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None
    completion_percent: int = Field(default=0, ge=0, le=100)

    @field_validator("title")
    @classmethod
    def title_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Milestone title must not be blank.")
        return value


class TaskWrite(MilestoneWrite):
    milestone_id: int | None = Field(default=None, gt=0)
    owner_user_id: int | None = Field(default=None, gt=0)


class MeetingWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    held_at: datetime
    minutes: str = Field(min_length=1, max_length=20000)
    decisions: str | None = Field(default=None, max_length=10000)
    action_items: list[dict[str, str]] = Field(default_factory=list, max_length=100)

    @field_validator("minutes")
    @classmethod
    def minutes_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Meeting minutes must not be blank.")
        return value


class ScheduleWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: int = Field(gt=0)
    academic_cycle_id: int = Field(gt=0)
    start_at: datetime
    end_at: datetime
    room: str | None = Field(default=None, max_length=255)
    online_link: str | None = Field(default=None, max_length=1000)
    panel_member_ids: list[int] = Field(default_factory=list, max_length=20)

    @field_validator("room", "online_link")
    @classmethod
    def blank_optional(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class ScheduleReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_at: datetime
    end_at: datetime
    room: str | None = Field(default=None, max_length=255)
    online_link: str | None = Field(default=None, max_length=1000)
    panel_member_ids: list[int] | None = Field(default=None, max_length=20)


class EvaluationScoreWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion_key: str = Field(min_length=1, max_length=160)
    score: int = Field(ge=0)
    max_score: int = Field(gt=0)
    feedback: str | None = Field(default=None, max_length=5000)


class EvaluationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schedule_id: int = Field(gt=0)
    scores: list[EvaluationScoreWrite] = Field(min_length=1, max_length=100)
    overall_score: int | None = Field(default=None, ge=0, le=100)
    overall_feedback: str | None = Field(default=None, max_length=10000)
    decision: str | None = Field(default=None, max_length=64)
    submit: bool = False


class ResolutionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(RECHECK_REQUESTED|RESOLVED)$")
    note: str = Field(min_length=1, max_length=10000)
