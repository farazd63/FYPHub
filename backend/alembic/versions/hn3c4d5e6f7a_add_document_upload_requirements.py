"""add admin-managed document upload requirements

Revision ID: hn3c4d5e6f7a
Revises: gm2b3c4d5e6f
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "hn3c4d5e6f7a"
down_revision = "gm2b3c4d5e6f"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("document_upload_requirements",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id"), nullable=False), sa.Column("module", sa.String(120), nullable=False),
        sa.Column("visible_to_roles", postgresql.JSONB(), nullable=False), sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("assigned_group_id", sa.Integer(), sa.ForeignKey("teams.id")),
        sa.Column("allowed_file_types", postgresql.JSONB(), nullable=False), sa.Column("max_file_size_mb", sa.Integer(), nullable=False, server_default="10"), sa.Column("due_at", sa.DateTime(timezone=True), nullable=False), sa.Column("reminder_days_before", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"), sa.Column("late_upload_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_document_requirements_status_due", "document_upload_requirements", ["status", "due_at"])
    op.create_index("ix_document_requirements_assigned_user", "document_upload_requirements", ["assigned_user_id"])
    op.create_table("document_submissions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("document_upload_requirements.id", ondelete="CASCADE"), nullable=False), sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="UPLOADED"), sa.Column("is_late", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("review_comment", sa.Text()), sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("reviewed_at", sa.DateTime(timezone=True)), sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("requirement_id", "student_id", name="uq_document_submission_requirement_student"))
    op.create_index("ix_document_submissions_student", "document_submissions", ["student_id"])
    op.create_table("document_submission_versions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("submission_id", sa.Integer(), sa.ForeignKey("document_submissions.id", ondelete="CASCADE"), nullable=False), sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("original_filename", sa.String(255), nullable=False), sa.Column("stored_filename", sa.String(255), nullable=False, unique=True), sa.Column("mime_type", sa.String(120), nullable=False), sa.Column("file_size", sa.Integer(), nullable=False), sa.Column("storage_reference", sa.String(500), nullable=False), sa.Column("content", sa.LargeBinary(), nullable=False), sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("submission_id", "version_number", name="uq_document_submission_version"))
    op.create_index("ix_document_versions_submission", "document_submission_versions", ["submission_id"])

def downgrade():
    op.drop_index("ix_document_versions_submission", table_name="document_submission_versions"); op.drop_table("document_submission_versions"); op.drop_index("ix_document_submissions_student", table_name="document_submissions"); op.drop_table("document_submissions"); op.drop_index("ix_document_requirements_assigned_user", table_name="document_upload_requirements"); op.drop_index("ix_document_requirements_status_due", table_name="document_upload_requirements"); op.drop_table("document_upload_requirements")
