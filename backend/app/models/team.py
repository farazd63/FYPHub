from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class Team(Base):
 __tablename__="teams"
 __table_args__=(UniqueConstraint("id","academic_cycle_id",name="uq_teams_id_cycle"),CheckConstraint("status IN ('forming','complete','locked','dissolved')",name="ck_teams_status"))
 id:Mapped[int]=mapped_column(primary_key=True)
 academic_cycle_id:Mapped[int]=mapped_column(ForeignKey("academic_cycles.id"),nullable=False)
 shared_user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),nullable=False,unique=True)
 status:Mapped[str]=mapped_column(String(16),nullable=False,default="forming",server_default="forming")
 locked_at:Mapped[datetime | None]=mapped_column(DateTime(timezone=True),nullable=True)
 lock_reason:Mapped[str | None]=mapped_column(String(64),nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())

class TeamMember(Base):
 __tablename__="team_members"
 __table_args__=(ForeignKeyConstraint(["team_id","academic_cycle_id"],["teams.id","teams.academic_cycle_id"]),UniqueConstraint("team_id","registration_number",name="uq_team_members_registration"),CheckConstraint("full_name=btrim(full_name) AND full_name<>''",name="ck_team_members_name"),CheckConstraint("registration_number=upper(btrim(registration_number)) AND registration_number<>''",name="ck_team_members_registration"),CheckConstraint("university_email=lower(btrim(university_email)) AND university_email<>''",name="ck_team_members_email"),Index("uq_active_cycle_registration","academic_cycle_id",text("lower(registration_number)"),unique=True,postgresql_where=text("is_active")),Index("uq_active_cycle_contact_email","academic_cycle_id",text("lower(university_email)"),unique=True,postgresql_where=text("is_active")),Index("uq_team_creator","team_id",unique=True,postgresql_where=text("is_creator")))
 id:Mapped[int]=mapped_column(primary_key=True);team_id:Mapped[int]=mapped_column(Integer,nullable=False);academic_cycle_id:Mapped[int]=mapped_column(Integer,nullable=False);full_name:Mapped[str]=mapped_column(String(255),nullable=False);registration_number:Mapped[str]=mapped_column(String(100),nullable=False);university_email:Mapped[str]=mapped_column(String(320),nullable=False);is_creator:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False,server_default="false");is_active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True,server_default="true");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now());updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
