from datetime import datetime
from pydantic import BaseModel, ConfigDict
class CycleOut(BaseModel):
 id:int; code:str; display_name:str; registration_open:bool; created_at:datetime; updated_at:datetime
 model_config=ConfigDict(from_attributes=True)
class PolicyOut(BaseModel):
 id:int; academic_cycle_id:int; max_group_size:int; created_at:datetime; updated_at:datetime
 model_config=ConfigDict(from_attributes=True)
