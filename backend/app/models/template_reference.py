from datetime import datetime
from enum import Enum
from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base
class TemplateType(str,Enum): SHORT="SHORT"; LONG="LONG"
class TemplateReference(Base):
 __tablename__="template_references"
 id:Mapped[int]=mapped_column(primary_key=True); template_type:Mapped[TemplateType]=mapped_column(SqlEnum(TemplateType,name="template_type"),unique=True,nullable=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now()); versions=relationship("TemplateReferenceVersion",back_populates="template_reference")
class TemplateReferenceVersion(Base):
 __tablename__="template_reference_versions"; __table_args__=(UniqueConstraint("template_reference_id","version_number",name="uq_template_reference_version"),)
 id:Mapped[int]=mapped_column(primary_key=True); template_reference_id:Mapped[int]=mapped_column(ForeignKey("template_references.id",ondelete="RESTRICT"),nullable=False); version_number:Mapped[int]=mapped_column(Integer,nullable=False); title:Mapped[str]=mapped_column(String(160),nullable=False); provenance:Mapped[str]=mapped_column(String(32),nullable=False); source_note:Mapped[str]=mapped_column(String(500),nullable=False); created_by_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"),nullable=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now()); is_active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False,server_default="false"); activated_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); activated_by_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"),nullable=True); template_reference=relationship("TemplateReference",back_populates="versions")
 @property
 def template_type(self): return self.template_reference.template_type
class AcademicRuleVersion(Base):
 __tablename__="academic_rule_versions"; __table_args__=(UniqueConstraint("template_reference_version_id","version_number",name="uq_academic_rule_version"),)
 id:Mapped[int]=mapped_column(primary_key=True); template_reference_version_id:Mapped[int]=mapped_column(ForeignKey("template_reference_versions.id",ondelete="RESTRICT"),nullable=False); version_number:Mapped[int]=mapped_column(Integer,nullable=False); provenance:Mapped[str]=mapped_column(String(32),nullable=False); rules:Mapped[dict]=mapped_column(JSONB,nullable=False); created_by_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"),nullable=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
