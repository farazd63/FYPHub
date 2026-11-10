from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from ..database import Base

class AcademicCycle(Base):
    __tablename__="academic_cycles"
    __table_args__=(CheckConstraint("code = upper(btrim(code)) AND code <> ''",name="ck_academic_cycles_code_normalized"),CheckConstraint("display_name = btrim(display_name) AND display_name <> ''",name="ck_academic_cycles_display_name_nonblank"),CheckConstraint("academic_year IS NULL OR academic_year BETWEEN 1900 AND 2200",name="ck_academic_cycles_year_valid"),CheckConstraint("session IS NULL OR session IN ('FALL','SPRING')",name="ck_academic_cycles_session_valid"),Index("uq_academic_cycles_code_normalized",text("lower(code)"),unique=True),Index("uq_academic_cycles_year_session", "academic_year", "session", unique=True, postgresql_where=text("academic_year IS NOT NULL AND session IS NOT NULL")))
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(100),nullable=False)
    display_name:Mapped[str]=mapped_column(String(255),nullable=False)
    academic_year:Mapped[int | None]=mapped_column(Integer,nullable=True)
    session:Mapped[str | None]=mapped_column(String(16),nullable=True)
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
    __table_args__=(
        CheckConstraint("max_group_size > 0",name="ck_academic_group_policies_max_group_size_positive"),
        CheckConstraint("min_group_size > 0 AND min_group_size <= max_group_size",name="ck_academic_group_policies_min_group_size_valid"),
    )
    id:Mapped[int]=mapped_column(primary_key=True)
    academic_cycle_id:Mapped[int]=mapped_column(ForeignKey("academic_cycles.id",ondelete="CASCADE"),nullable=False,unique=True)
    max_group_size:Mapped[int]=mapped_column(Integer,nullable=False)
    min_group_size:Mapped[int]=mapped_column(Integer,nullable=False,default=1,server_default="1")
    formation_deadline:Mapped[datetime | None]=mapped_column(DateTime(timezone=True),nullable=True)
    matching_weights:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict,server_default="{}")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
    academic_cycle:Mapped[AcademicCycle]=relationship(back_populates="group_policy")

class SupervisorCapacityPolicy(Base):
    __tablename__="supervisor_capacity_policies"
    __table_args__=(
        CheckConstraint("max_group_capacity > 0",name="ck_supervisor_capacity_policies_capacity_positive"),
        CheckConstraint("academic_year IS NULL OR academic_year BETWEEN 1900 AND 2200",name="ck_supervisor_capacity_policies_year_valid"),
        UniqueConstraint("supervisor_id", "academic_year", name="uq_supervisor_capacity_policies_supervisor_year"),
    )
    id:Mapped[int]=mapped_column(primary_key=True)
    supervisor_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"),nullable=False)
    academic_cycle_id:Mapped[int | None]=mapped_column(ForeignKey("academic_cycles.id",ondelete="RESTRICT"),nullable=True)
    academic_year:Mapped[int | None]=mapped_column(Integer,nullable=True)
    max_group_capacity:Mapped[int]=mapped_column(Integer,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
    supervisor:Mapped["User"]=relationship("User")
    academic_cycle:Mapped[AcademicCycle | None]=relationship("AcademicCycle")
