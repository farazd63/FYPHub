"""Persist archive import batches and append-safe duplicate keys."""

from alembic import op
import sqlalchemy as sa

revision = "re8f9a0b1c2d"
down_revision = "rd7e8f9a0b1c"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("archived_projects")}
    if "normalized_group_name" not in columns:
        op.add_column("archived_projects", sa.Column("normalized_group_name", sa.String(length=255), nullable=False, server_default=""))
        op.alter_column("archived_projects", "normalized_group_name", server_default=None)
    if "group_name" not in columns:
        op.add_column("archived_projects", sa.Column("group_name", sa.String(length=255), nullable=True))
    if "source_batch_id" not in columns:
        op.add_column("archived_projects", sa.Column("source_batch_id", sa.String(length=64), nullable=True))
    if "source_row_number" not in columns:
        op.add_column("archived_projects", sa.Column("source_row_number", sa.Integer(), nullable=True))
    indexes = {item["name"] for item in inspector.get_indexes("archived_projects")}
    if "uq_archived_project_active_title_year" in indexes:
        op.drop_index("uq_archived_project_active_title_year", table_name="archived_projects")
    if "uq_archived_project_active_title_year_group" not in indexes:
        op.create_index("uq_archived_project_active_title_year_group", "archived_projects", ["normalized_title", "academic_year", "normalized_group_name"], unique=True, postgresql_where=sa.text("is_active = true"))
    if "ix_archived_projects_source_batch_id" not in indexes:
        op.create_index("ix_archived_projects_source_batch_id", "archived_projects", ["source_batch_id"], unique=False)
    if "archive_import_batches" not in inspector.get_table_names():
        op.create_table(
            "archive_import_batches",
            sa.Column("batch_id", sa.String(length=64), primary_key=True),
            sa.Column("original_file_name", sa.String(length=255), nullable=False),
            sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("inserted_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("import_status", sa.String(length=32), nullable=False, server_default="PROCESSING"),
        )


def downgrade():
    op.drop_table("archive_import_batches")
    op.drop_index("ix_archived_projects_source_batch_id", table_name="archived_projects")
    op.drop_index("uq_archived_project_active_title_year_group", table_name="archived_projects")
    op.create_index("uq_archived_project_active_title_year", "archived_projects", ["normalized_title", "academic_year"], unique=True, postgresql_where=sa.text("is_active = true"))
    for name in ("source_row_number", "source_batch_id", "group_name", "normalized_group_name"):
        op.drop_column("archived_projects", name)
