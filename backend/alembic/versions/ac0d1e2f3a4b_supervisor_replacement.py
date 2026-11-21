"""Add administrator-led supervisor replacement and assignment history fields."""

from alembic import op
import sqlalchemy as sa


revision = "ac0d1e2f3a4b"
down_revision = "ab9c0d1e2f3a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("supervision_status", sa.String(24), nullable=False, server_default="ACTIVE"))
    op.create_check_constraint("ck_teams_supervision_status", "teams", "supervision_status IN ('ACTIVE','UNSUPERVISED','REPLACEMENT_PENDING','REASSIGNED','COMPLETED')")
    op.add_column("supervisor_assignments", sa.Column("end_reason", sa.String(32), nullable=True))
    op.add_column("supervisor_assignments", sa.Column("end_notes", sa.String(2000), nullable=True))

    op.create_table(
        "supervisor_departures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("marked_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
    )
    op.create_index("ix_supervisor_departures_institution_id", "supervisor_departures", ["institution_id"])
    op.create_index("uq_supervisor_departures_active", "supervisor_departures", ["supervisor_id"], unique=True, postgresql_where=sa.text("active = true"))
    op.create_index("ix_supervisor_departures_supervisor_active", "supervisor_departures", ["supervisor_id", "active"])

    op.create_table(
        "supervisor_replacement_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_assignment_id", sa.Integer(), sa.ForeignKey("supervisor_assignments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("replacement_assignment_id", sa.Integer(), sa.ForeignKey("supervisor_assignments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("replacement_supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="UNSUPERVISED"),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("opened_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("assigned_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
    )
    op.create_index("ix_supervisor_replacement_cases_institution_id", "supervisor_replacement_cases", ["institution_id"])
    op.create_index("ix_supervisor_replacement_cases_status", "supervisor_replacement_cases", ["status", "opened_at"])
    op.create_index("ix_supervisor_replacement_cases_team", "supervisor_replacement_cases", ["team_id", "academic_cycle_id"])


def downgrade() -> None:
    op.drop_index("ix_supervisor_replacement_cases_team", table_name="supervisor_replacement_cases")
    op.drop_index("ix_supervisor_replacement_cases_status", table_name="supervisor_replacement_cases")
    op.drop_index("ix_supervisor_replacement_cases_institution_id", table_name="supervisor_replacement_cases")
    op.drop_table("supervisor_replacement_cases")
    op.drop_index("ix_supervisor_departures_supervisor_active", table_name="supervisor_departures")
    op.drop_index("uq_supervisor_departures_active", table_name="supervisor_departures")
    op.drop_index("ix_supervisor_departures_institution_id", table_name="supervisor_departures")
    op.drop_table("supervisor_departures")
    op.drop_column("supervisor_assignments", "end_notes")
    op.drop_column("supervisor_assignments", "end_reason")
    op.drop_constraint("ck_teams_supervision_status", "teams", type_="check")
    op.drop_column("teams", "supervision_status")
