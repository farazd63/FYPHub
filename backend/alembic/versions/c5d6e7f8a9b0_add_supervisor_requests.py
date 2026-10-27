"""add student supervisor-selection requests and immutable history"""

from alembic import op
import sqlalchemy as sa


revision = "c5d6e7f8a9b0"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


STATUSES = "'DRAFT','SUBMITTED','CHANGES_REQUESTED','ACCEPTED','REJECTED','WITHDRAWN'"


def upgrade():
    op.create_table(
        "supervisor_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requester_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("supervisor_assignments.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.ForeignKeyConstraint(["team_id", "academic_cycle_id"], ["teams.id", "teams.academic_cycle_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("revision > 0", name="ck_supervisor_requests_revision_positive"),
        sa.CheckConstraint("title = btrim(title) AND title <> ''", name="ck_supervisor_requests_title_nonblank"),
        sa.CheckConstraint("summary = btrim(summary) AND summary <> ''", name="ck_supervisor_requests_summary_nonblank"),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_supervisor_requests_status"),
    )
    op.create_index("ix_supervisor_requests_cycle_status", "supervisor_requests", ["academic_cycle_id", "status"])
    op.create_index("ix_supervisor_requests_supervisor_status", "supervisor_requests", ["supervisor_id", "status"])
    op.create_index("uq_supervisor_requests_active_owner_supervisor", "supervisor_requests", ["academic_cycle_id", "requester_user_id", "supervisor_id"], unique=True, postgresql_where=sa.text("status IN ('DRAFT','SUBMITTED','CHANGES_REQUESTED','ACCEPTED')"))
    op.create_table(
        "supervisor_request_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"to_status IN ({STATUSES})", name="ck_supervisor_request_history_to_status"),
    )
    op.create_index("ix_supervisor_request_history_request_created", "supervisor_request_status_history", ["request_id", "created_at"])
    op.execute("CREATE FUNCTION prevent_supervisor_request_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'supervisor request history is append-only'; END $$")
    op.execute("CREATE TRIGGER supervisor_request_history_append_only BEFORE UPDATE OR DELETE ON supervisor_request_status_history FOR EACH ROW EXECUTE FUNCTION prevent_supervisor_request_history_mutation()")


def downgrade():
    op.execute("DROP TRIGGER supervisor_request_history_append_only ON supervisor_request_status_history")
    op.execute("DROP FUNCTION prevent_supervisor_request_history_mutation()")
    op.drop_index("ix_supervisor_request_history_request_created", table_name="supervisor_request_status_history")
    op.drop_table("supervisor_request_status_history")
    op.drop_index("uq_supervisor_requests_active_owner_supervisor", table_name="supervisor_requests")
    op.drop_index("ix_supervisor_requests_supervisor_status", table_name="supervisor_requests")
    op.drop_index("ix_supervisor_requests_cycle_status", table_name="supervisor_requests")
    op.drop_table("supervisor_requests")
