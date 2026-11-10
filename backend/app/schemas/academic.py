from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict
from pydantic import field_validator

class AcademicSession(str, Enum):
 FALL = "FALL"
 SPRING = "SPRING"

class CycleOut(BaseModel):
 id:int; code:str; display_name:str; academic_year:int|None = None; session:AcademicSession|None = None; registration_open:bool; created_at:datetime; updated_at:datetime
 model_config=ConfigDict(from_attributes=True)
class PolicyOut(BaseModel):
 id:int; academic_cycle_id:int; max_group_size:int; min_group_size:int = 1; formation_deadline:datetime|None = None; matching_weights:dict = {}; created_at:datetime; updated_at:datetime
 model_config=ConfigDict(from_attributes=True)
class CycleCreate(BaseModel):
 model_config=ConfigDict(extra="forbid")
 academic_year:int; session:AcademicSession
 @field_validator("session", mode="before")
 @classmethod
 def session_value(cls,value:object)->object:
  return value.strip().upper() if isinstance(value,str) else value
 @field_validator("academic_year")
 @classmethod
 def year_value(cls,value:int)->int:
  if value<1900 or value>2200: raise ValueError("academic_year must be between 1900 and 2200.")
  return value
class CycleUpdate(BaseModel):
 model_config=ConfigDict(extra="forbid")
 code:str|None=None; display_name:str|None=None; registration_open:bool|None=None
 @field_validator("code")
 @classmethod
 def update_code(cls,value:str|None)->str|None:
  value=value.strip().upper() if value is not None else value
  if value is not None and (not value or len(value)>100): raise ValueError("code must be between 1 and 100 characters.")
  return value
 @field_validator("display_name")
 @classmethod
 def update_name(cls,value:str|None)->str|None:
  value=value.strip() if value is not None else value
  if value is not None and (not value or len(value)>255): raise ValueError("display_name must be between 1 and 255 characters.")
  return value
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
