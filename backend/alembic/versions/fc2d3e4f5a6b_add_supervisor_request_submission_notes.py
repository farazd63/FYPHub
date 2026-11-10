"""add optional immutable supervisor-request submission note versions"""

from alembic import op
import sqlalchemy as sa


revision = "fc2d3e4f5a6b"
down_revision = "fa0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("supervisor_requests", sa.Column("submission_note", sa.Text(), nullable=True))
    op.create_table(
        "supervisor_request_submission_note_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_supervisor_request_note_version_positive"),
        sa.CheckConstraint("body = btrim(body) AND body <> ''", name="ck_supervisor_request_note_body_nonblank"),
    )
    op.create_index("uq_supervisor_request_note_version", "supervisor_request_submission_note_versions", ["request_id", "version"], unique=True)
    op.create_index("ix_supervisor_request_note_request", "supervisor_request_submission_note_versions", ["request_id", "submitted_at"])
    op.execute("CREATE FUNCTION prevent_supervisor_request_note_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'supervisor request submission notes are immutable'; END $$")
    op.execute("CREATE TRIGGER supervisor_request_note_append_only BEFORE UPDATE OR DELETE ON supervisor_request_submission_note_versions FOR EACH ROW EXECUTE FUNCTION prevent_supervisor_request_note_mutation()")


def downgrade():
    op.execute("DROP TRIGGER supervisor_request_note_append_only ON supervisor_request_submission_note_versions")
    op.execute("DROP FUNCTION prevent_supervisor_request_note_mutation()")
    op.drop_index("ix_supervisor_request_note_request", table_name="supervisor_request_submission_note_versions")
    op.drop_index("uq_supervisor_request_note_version", table_name="supervisor_request_submission_note_versions")
    op.drop_table("supervisor_request_submission_note_versions")
    op.drop_column("supervisor_requests", "submission_note")
