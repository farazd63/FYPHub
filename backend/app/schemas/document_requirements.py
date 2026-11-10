from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

TYPES = {"pdf", "doc", "docx", "tex", "txt", "md", "jpg", "jpeg", "png", "gif", "webp", "svg", "mp4", "mov", "avi", "mkv", "webm", "mp3", "wav", "m4a", "ogg", "xls", "xlsx", "csv", "ppt", "pptx", "zip", "rar", "7z"}
class RequirementWrite(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_date: datetime | None = None
    assigned_to: str | None = None
    description: str | None = None
    academic_cycle_id: int | None = Field(default=None, gt=0)
    module: str = "General"
    visible_to_roles: list[str] = ["STUDENT"]
    assigned_user_id: int | None = Field(default=None, gt=0)
    assigned_group_id: int | None = Field(default=None, gt=0)
    allowed_file_types: list[str] = ["pdf"]
    max_file_size_mb: int = Field(default=10, ge=1, le=100)
    due_at: datetime | None = None
    reminder_days_before: int = Field(default=3, ge=0, le=365)
    is_required: bool = True
    late_upload_allowed: bool = False
    @field_validator("assigned_to")
    @classmethod
    def assignment(cls, value):
        if value is not None and not value.strip(): raise ValueError("Assigned To must not be blank.")
        return value.strip() if value else "ALL_STUDENTS"
    @field_validator("allowed_file_types")
    @classmethod
    def file_types(cls, value):
        normalized = [item.lower().lstrip(".") for item in value]
        if not normalized or any(item not in TYPES for item in normalized): raise ValueError("One or more file formats are not supported.")
        return list(dict.fromkeys(normalized))

    @field_validator("due_date", "due_at", mode="after")
    @classmethod
    def deadline(cls, value):
        if value is None: return value
        return value

class RequirementPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    due_at: datetime | None = None
    allowed_file_types: list[str] | None = None
    max_file_size_mb: int | None = Field(default=None, ge=1, le=100)
    reminder_days_before: int | None = Field(default=None, ge=0, le=365)
    late_upload_allowed: bool | None = None

class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; title: str; description: str | None; academic_cycle_id: int; module: str; visible_to_roles: list; assigned_user_id: int | None; assigned_group_id: int | None; allowed_file_types: list; max_file_size_mb: int; due_at: datetime; reminder_days_before: int; is_required: bool; status: str; late_upload_allowed: bool; created_at: datetime; updated_at: datetime

class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; version_number: int; original_filename: str; mime_type: str; file_size: int; storage_reference: str; uploaded_at: datetime

class SubmissionOut(BaseModel):
    id: int; requirement_id: int; status: str; is_late: bool; review_comment: str | None; uploaded_at: datetime; updated_at: datetime; versions: list[VersionOut] = []
