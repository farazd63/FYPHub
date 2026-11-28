"""Add document-linked supervisor training sessions."""

from alembic import op
import sqlalchemy as sa


revision = "z7d4e5f6g7h8"
down_revision = "z7c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_training_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("supervisor_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=True),
        sa.Column("submission_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("meeting_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="SCHEDULED"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("status IN ('SCHEDULED','COMPLETED','CANCELLED')", name="ck_document_training_sessions_status"),
        sa.CheckConstraint("duration_minutes >= 15 AND duration_minutes <= 480", name="ck_document_training_sessions_duration"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supervisor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requirement_id"], ["document_upload_requirements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submission_id"], ["document_submissions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_document_training_sessions_team_schedule", "document_training_sessions", ["team_id", "scheduled_at"])
    op.create_index("ix_document_training_sessions_requirement", "document_training_sessions", ["requirement_id", "created_at"])
    op.create_index("ix_document_training_sessions_institution_id", "document_training_sessions", ["institution_id"])


def downgrade() -> None:
    op.drop_index("ix_document_training_sessions_institution_id", table_name="document_training_sessions")
    op.drop_index("ix_document_training_sessions_requirement", table_name="document_training_sessions")
    op.drop_index("ix_document_training_sessions_team_schedule", table_name="document_training_sessions")
    op.drop_table("document_training_sessions")
