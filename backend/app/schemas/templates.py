from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from ..models import TemplateType
class RuleFields(BaseModel):
 model_config=ConfigDict(extra="forbid")
 page_size:str|None=None; font_family:str|None=None; font_size_pt:float|None=Field(default=None,gt=0); margin_mm:float|None=Field(default=None,gt=0); line_spacing:float|None=Field(default=None,gt=0); heading_style:str|None=None
class TemplateCreate(BaseModel):
 model_config=ConfigDict(extra="forbid"); template_type:TemplateType; title:str=Field(min_length=1,max_length=160); provenance:str=Field(pattern="^(OBSERVED_REFERENCE|CONFIRMED_REQUIREMENT)$"); source_note:str=Field(min_length=1,max_length=500); rules:RuleFields=Field(default_factory=RuleFields)
class TemplateVersionCreate(BaseModel):
 model_config=ConfigDict(extra="forbid"); title:str=Field(min_length=1,max_length=160); provenance:str=Field(pattern="^(OBSERVED_REFERENCE|CONFIRMED_REQUIREMENT)$"); source_note:str=Field(min_length=1,max_length=500)
class RuleCreate(BaseModel):
 model_config=ConfigDict(extra="forbid"); provenance:str=Field(pattern="^(OBSERVED_REFERENCE|CONFIRMED_REQUIREMENT)$"); rules:RuleFields=Field(default_factory=RuleFields)
class TemplateOut(BaseModel):
 id:int; template_type:TemplateType; version_number:int; title:str; provenance:str; source_note:str; created_at:datetime; model_config=ConfigDict(from_attributes=True)
class TemplateListOut(TemplateOut):
 reference_id:int
class RuleOut(BaseModel):
 id:int; template_reference_version_id:int; version_number:int; provenance:str; rules:dict; created_at:datetime; model_config=ConfigDict(from_attributes=True)
class TemplateHistoryVersion(BaseModel):
 template:TemplateOut; rules:list[RuleOut]
class TemplateDetail(BaseModel):
 reference_id:int; template_type:TemplateType; versions:list[TemplateHistoryVersion]
