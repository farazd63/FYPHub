"""add persisted progress, defense scheduling, and panel evaluation workflows"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "ff5a6b7c8d9e"
down_revision = "fe4f5a6b7c8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_milestones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("completion_percent >= 0 AND completion_percent <= 100", name="ck_project_milestones_completion"),
    )
    op.create_index("ix_project_milestones_team_due", "project_milestones", ["team_id", "due_at"])
    op.create_table(
        "project_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("milestone_id", sa.Integer(), sa.ForeignKey("project_milestones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("completion_percent >= 0 AND completion_percent <= 100", name="ck_project_tasks_completion"),
    )
    op.create_index("ix_project_tasks_team_due", "project_tasks", ["team_id", "due_at"])
    op.create_table(
        "supervision_meetings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("held_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minutes", sa.Text(), nullable=False),
        sa.Column("decisions", sa.Text(), nullable=True),
        sa.Column("action_items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_supervision_meetings_team_held", "supervision_meetings", ["team_id", "held_at"])
    op.create_table(
        "defense_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("room", sa.String(255), nullable=True),
        sa.Column("online_link", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="SCHEDULED"),
        sa.Column("conflict_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("end_at > start_at", name="ck_defense_schedules_time_order"),
        sa.CheckConstraint("status IN ('SCHEDULED','RESCHEDULED','CANCELLED')", name="ck_defense_schedules_status"),
    )
    op.create_index("ix_defense_schedules_time", "defense_schedules", ["start_at", "end_at"])
    op.create_table(
        "defense_panel_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("defense_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("schedule_id", "user_id", name="uq_defense_panel_member"),
    )
    op.create_table(
        "panel_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("defense_schedules.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evaluator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("overall_feedback", sa.Text(), nullable=True),
        sa.Column("decision", sa.String(64), nullable=True),
        sa.Column("disagreement_detected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('DRAFT','SUBMITTED','RECHECK_REQUESTED','RESOLVED')", name="ck_panel_evaluations_status"),
        sa.CheckConstraint("overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)", name="ck_panel_evaluations_score"),
        sa.UniqueConstraint("schedule_id", "evaluator_id", name="uq_panel_evaluation_schedule_evaluator"),
    )
    op.create_table(
        "panel_evaluation_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("panel_evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("criterion_key", sa.String(160), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.CheckConstraint("score >= 0 AND max_score > 0 AND score <= max_score", name="ck_panel_evaluation_scores_range"),
        sa.UniqueConstraint("evaluation_id", "criterion_key", name="uq_panel_evaluation_score_criterion"),
    )


def downgrade() -> None:
    op.drop_table("panel_evaluation_scores")
    op.drop_table("panel_evaluations")
    op.drop_table("defense_panel_members")
    op.drop_index("ix_defense_schedules_time", table_name="defense_schedules")
    op.drop_table("defense_schedules")
    op.drop_index("ix_supervision_meetings_team_held", table_name="supervision_meetings")
    op.drop_table("supervision_meetings")
    op.drop_index("ix_project_tasks_team_due", table_name="project_tasks")
    op.drop_table("project_tasks")
    op.drop_index("ix_project_milestones_team_due", table_name="project_milestones")
    op.drop_table("project_milestones")
