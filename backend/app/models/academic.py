from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from ..database import Base

class AcademicCycle(Base):
    __tablename__="academic_cycles"
    __table_args__=(CheckConstraint("code = upper(btrim(code)) AND code <> ''",name="ck_academic_cycles_code_normalized"),CheckConstraint("display_name = btrim(display_name) AND display_name <> ''",name="ck_academic_cycles_display_name_nonblank"),Index("uq_academic_cycles_code_normalized",text("lower(code)"),unique=True))
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(100),nullable=False)
    display_name:Mapped[str]=mapped_column(String(255),nullable=False)
    registration_open:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False,server_default="false")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
    group_policy:Mapped["AcademicGroupPolicy | None"]=relationship(back_populates="academic_cycle",uselist=False)
    @validates("code")
    def norm_code(self,_:str,value:str)->str:return value.strip().upper()
    @validates("display_name")
    def norm_name(self,_:str,value:str)->str:return value.strip()

class AcademicGroupPolicy(Base):
    __tablename__="academic_group_policies"
    __table_args__=(CheckConstraint("max_group_size > 0",name="ck_academic_group_policies_max_group_size_positive"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    academic_cycle_id:Mapped[int]=mapped_column(ForeignKey("academic_cycles.id",ondelete="CASCADE"),nullable=False,unique=True)
    max_group_size:Mapped[int]=mapped_column(Integer,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
    academic_cycle:Mapped[AcademicCycle]=relationship(back_populates="group_policy")

class SupervisorCapacityPolicy(Base):
    __tablename__="supervisor_capacity_policies"
    __table_args__=(
        CheckConstraint("max_group_capacity > 0",name="ck_supervisor_capacity_policies_capacity_positive"),
        UniqueConstraint("supervisor_id", "academic_cycle_id", name="uq_supervisor_capacity_policies_supervisor_cycle"),
    )
    id:Mapped[int]=mapped_column(primary_key=True)
    supervisor_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"),nullable=False)
    academic_cycle_id:Mapped[int]=mapped_column(ForeignKey("academic_cycles.id",ondelete="RESTRICT"),nullable=False)
    max_group_capacity:Mapped[int]=mapped_column(Integer,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
    supervisor:Mapped["User"]=relationship("User")
    academic_cycle:Mapped[AcademicCycle]=relationship("AcademicCycle")
