from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, StrictInt, Field


class CapacitySession(StrEnum):
    FALL = "FALL"
    SPRING = "SPRING"


class SupervisorCapacityWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supervisor_id: StrictInt
    academic_year: StrictInt = Field(ge=1900, le=2200)
    maximum_groups: StrictInt = Field(gt=0)


class SupervisorCapacityOut(BaseModel):
    id: int
    supervisor_id: int
    supervisor_name: str
    supervisor_email: str
    supervisor_is_eligible: bool
    academic_year: int | None
    maximum_groups: int
    fall_assigned: int
    spring_assigned: int
    total_assigned: int
    remaining_capacity: int
    status: str
    # Legacy fields remain in the response while existing clients migrate.
    academic_cycle_id: int | None = None
    academic_cycle_name: str | None = None
    max_group_capacity: int | None = None
    assigned_groups: int | None = None
    remaining_groups: int | None = None
    session: CapacitySession | None = None
    assigned: int | None = None
    remaining: int | None = None
    full: bool | None = None
    created_at: datetime
    updated_at: datetime
