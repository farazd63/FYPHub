"""Strict deadline configuration and timezone-preview schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeadlinePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_due_at: str = Field(min_length=16, max_length=19)
    time_zone: str = Field(min_length=1, max_length=100)
    utc_offset: str | None = Field(default=None, pattern=r"^[+-](?:0\d|1\d|2[0-3]):[0-5]\d$")

    @field_validator("local_due_at")
    @classmethod
    def validate_wall_time(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Local due time must be an ISO local date and time.") from error
        if parsed.tzinfo is not None:
            raise ValueError("Local due time must not contain an offset; submit the offset separately.")
        return value

    @field_validator("time_zone")
    @classmethod
    def nonblank_zone(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Time zone must not be blank.")
        return value


class DeadlineWrite(DeadlinePreviewRequest):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    due_at_utc: datetime

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Deadline name must not be blank.")
        return value


    @field_validator("due_at_utc")
    @classmethod
    def aware_due_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Canonical due time must include an offset.")
        return value

class DeadlineCreate(DeadlineWrite):
    academic_cycle_id: int = Field(gt=0)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class DeadlinePreviewOut(BaseModel):
    local_due_at: str
    time_zone: str
    utc_offset: str
    due_at_utc: datetime


class DeadlineVersionOut(DeadlinePreviewOut):
    id: int
    version_number: int
    name: str
    description: str | None
    created_at: datetime


class DeadlineDetailOut(BaseModel):
    id: int
    academic_cycle_id: int
    academic_cycle_name: str
    created_at: datetime
    versions: list[DeadlineVersionOut]


class DeadlineListOut(BaseModel):
    id: int
    academic_cycle_id: int
    academic_cycle_name: str
    name: str
    description: str | None
    latest_version_number: int
    due_at_utc: datetime
    local_due_at: str
    time_zone: str
    utc_offset: str
