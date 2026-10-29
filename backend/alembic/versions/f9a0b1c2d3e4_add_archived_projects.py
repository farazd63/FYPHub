"""add logical archived projects and immutable document versions"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f9a0b1c2d3e4"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "archived_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("normalized_title", sa.String(length=255), nullable=False),
        sa.Column("abstract_summary", sa.Text(), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.String(length=100)), server_default="{}", nullable=False),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("academic_year", sa.String(length=64), nullable=False),
        sa.Column("department_program", sa.String(length=255), nullable=False),
        sa.Column("project_scope", sa.String(length=255), nullable=False),
        sa.Column("completion_stage", sa.String(length=100), nullable=False),
        sa.Column("implemented_scope", sa.Text(), nullable=False),
        sa.Column("remaining_gaps", sa.Text(), nullable=False),
        sa.Column("future_work", sa.Text(), nullable=False),
        sa.Column("supervisor_display_reference", sa.String(length=255), nullable=True),
        sa.Column("source_label", sa.String(length=64), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("normalized_title", "academic_year", name="uq_archived_project_title_year"),
    )
    op.create_index("ix_archived_projects_normalized_title", "archived_projects", ["normalized_title"])
    op.create_index("ix_archived_projects_active_cycle", "archived_projects", ["is_active", "academic_year"])
    op.create_index("ix_archived_projects_active_scope", "archived_projects", ["is_active", "project_scope"])
    op.create_table(
        "archived_project_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("archived_project_id", sa.Integer(), sa.ForeignKey("archived_projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_archived_project_documents_project_type", "archived_project_documents", ["archived_project_id", "document_type", "version"])
    op.create_index("uq_archived_project_active_document_type", "archived_project_documents", ["archived_project_id", "document_type"], unique=True, postgresql_where=sa.text("is_active = true"))


def downgrade():
    op.drop_index("uq_archived_project_active_document_type", table_name="archived_project_documents")
    op.drop_index("ix_archived_project_documents_project_type", table_name="archived_project_documents")
    op.drop_table("archived_project_documents")
    op.drop_index("ix_archived_projects_active_scope", table_name="archived_projects")
    op.drop_index("ix_archived_projects_active_cycle", table_name="archived_projects")
    op.drop_index("ix_archived_projects_normalized_title", table_name="archived_projects")
    op.drop_table("archived_projects")
