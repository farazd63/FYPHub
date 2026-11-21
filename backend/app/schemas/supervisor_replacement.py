"""Administrator supervisor replacement contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReplacementReason = Literal["LEFT_UNIVERSITY", "RESIGNED", "UNAVAILABLE", "REMOVED", "LONG_TERM_LEAVE"]
ReplacementStatus = Literal["ACTIVE", "UNSUPERVISED", "REPLACEMENT_PENDING", "REASSIGNED", "COMPLETED"]


class DepartureWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: ReplacementReason
    notes: str | None = Field(default=None, max_length=2000)


class DepartureRestoreWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=2000)


class ReplacementAssignWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supervisor_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=2000)


class ReplacementCompleteWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=2000)
