from datetime import datetime
from pydantic import BaseModel, ConfigDict, StrictInt, Field


class SupervisorCapacityWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supervisor_id: StrictInt
    academic_cycle_id: StrictInt
    max_group_capacity: StrictInt = Field(gt=0)


class SupervisorCapacityOut(BaseModel):
    id: int
    supervisor_id: int
    supervisor_name: str
    supervisor_email: str
    supervisor_is_eligible: bool
    academic_cycle_id: int
    academic_cycle_name: str
    max_group_capacity: int
    assigned: int
    remaining: int
    full: bool
    created_at: datetime
    updated_at: datetime
