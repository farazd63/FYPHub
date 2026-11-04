"""restore the role-based FYP evaluation and results module"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "mn7c8d9e0f1a"
down_revision = "lm6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("evaluator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evaluator_role", sa.String(32), nullable=False),
        sa.Column("evaluation_category", sa.String(32), nullable=False),
        sa.Column("maximum_marks", sa.Integer(), nullable=False),
        sa.Column("obtained_marks", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("returned_reason", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("(student_id IS NOT NULL AND group_id IS NULL) OR (student_id IS NULL AND group_id IS NOT NULL)", name="ck_evaluation_one_target"),
        sa.CheckConstraint("evaluation_category IN ('FINAL_PRESENTATION','MID_REVIEW','SUPERVISOR_EVALUATION','PROJECT_DOCUMENTATION','PROPOSAL')", name="ck_evaluation_category"),
        sa.CheckConstraint("status IN ('DRAFT','SUBMITTED','RETURNED','APPROVED','PUBLISHED')", name="ck_evaluation_status"),
        sa.CheckConstraint("obtained_marks IS NULL OR (obtained_marks >= 0 AND obtained_marks <= maximum_marks)", name="ck_evaluation_marks_range"),
        sa.CheckConstraint("maximum_marks IN (30, 10, 20)", name="ck_evaluation_maximum"),
        sa.UniqueConstraint("student_id", "evaluation_category", "evaluator_id", name="uq_evaluation_student_category_evaluator"),
        sa.UniqueConstraint("group_id", "evaluation_category", "evaluator_id", name="uq_evaluation_group_category_evaluator"),
    )
    op.create_index("ix_evaluation_records_category_status", "evaluation_records", ["evaluation_category", "status"])
    op.create_index("ix_evaluation_records_evaluator", "evaluation_records", ["evaluator_id", "status"])
    op.create_index("ix_evaluation_records_student", "evaluation_records", ["student_id"])
    op.create_index("ix_evaluation_records_group", "evaluation_records", ["group_id"])

    op.create_table(
        "evaluation_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("evaluation_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("previous_marks", sa.Integer(), nullable=True),
        sa.Column("new_marks", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_values", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_audit_record_created", "evaluation_audit_events", ["evaluation_id", "created_at"])

    op.create_table(
        "evaluation_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("evaluation_records.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("authorized_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_marks", sa.Integer(), nullable=False),
        sa.Column("new_marks", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_corrections_evaluation", "evaluation_corrections", ["evaluation_id", "created_at"])

    op.create_table(
        "evaluation_aggregation_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_category", sa.String(32), nullable=False),
        sa.Column("method", sa.String(16), nullable=False, server_default="AVERAGE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("evaluation_category IN ('FINAL_PRESENTATION','MID_REVIEW')", name="ck_evaluation_aggregation_category"),
        sa.CheckConstraint("method IN ('AVERAGE','MAXIMUM','MEDIAN')", name="ck_evaluation_aggregation_method"),
        sa.UniqueConstraint("evaluation_category", name="uq_evaluation_aggregation_category"),
    )


def downgrade() -> None:
    op.drop_table("evaluation_aggregation_configs")
    op.drop_index("ix_evaluation_corrections_evaluation", table_name="evaluation_corrections")
    op.drop_table("evaluation_corrections")
    op.drop_index("ix_evaluation_audit_record_created", table_name="evaluation_audit_events")
    op.drop_table("evaluation_audit_events")
    op.drop_index("ix_evaluation_records_group", table_name="evaluation_records")
    op.drop_index("ix_evaluation_records_student", table_name="evaluation_records")
    op.drop_index("ix_evaluation_records_evaluator", table_name="evaluation_records")
    op.drop_index("ix_evaluation_records_category_status", table_name="evaluation_records")
    op.drop_table("evaluation_records")
