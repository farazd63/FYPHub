from datetime import datetime
from pydantic import BaseModel, ConfigDict
from pydantic import field_validator
class CycleOut(BaseModel):
 id:int; code:str; display_name:str; registration_open:bool; created_at:datetime; updated_at:datetime
 model_config=ConfigDict(from_attributes=True)
class PolicyOut(BaseModel):
 id:int; academic_cycle_id:int; max_group_size:int; min_group_size:int = 1; formation_deadline:datetime|None = None; matching_weights:dict = {}; created_at:datetime; updated_at:datetime
 model_config=ConfigDict(from_attributes=True)
class CycleCreate(BaseModel):
 model_config=ConfigDict(extra="forbid")
 code:str; display_name:str
 @field_validator("code")
 @classmethod
 def code_value(cls,value:str)->str:
  value=value.strip().upper()
  if not value or len(value)>100: raise ValueError("code must be between 1 and 100 characters.")
  return value
 @field_validator("display_name")
 @classmethod
 def name_value(cls,value:str)->str:
  value=value.strip()
  if not value or len(value)>255: raise ValueError("display_name must be between 1 and 255 characters.")
  return value
class CycleUpdate(BaseModel):
 model_config=ConfigDict(extra="forbid")
 code:str|None=None; display_name:str|None=None; registration_open:bool|None=None
 @field_validator("code")
 @classmethod
 def update_code(cls,value:str|None)->str|None:return CycleCreate.code_value(value) if value is not None else value
 @field_validator("display_name")
 @classmethod
 def update_name(cls,value:str|None)->str|None:return CycleCreate.name_value(value) if value is not None else value
class PolicyUpdate(BaseModel):
 model_config=ConfigDict(extra="forbid")
 max_group_size:int; min_group_size:int = 1; formation_deadline:datetime|None = None; matching_weights:dict = {}
 @field_validator("max_group_size")
 @classmethod
 def positive(cls,value:int)->int:
  if value<=0: raise ValueError("max_group_size must be positive.")
  return value
 @field_validator("min_group_size")
 @classmethod
 def minimum_positive(cls,value:int)->int:
  if value<=0: raise ValueError("min_group_size must be positive.")
  return value
