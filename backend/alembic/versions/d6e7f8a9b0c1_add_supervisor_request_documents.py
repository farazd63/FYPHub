"""add immutable one-page proposal documents and extraction snapshots"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


STATUSES = "'DRAFT','SUBMITTED','CHANGES_REQUESTED','ACCEPTED','REJECTED','WITHDRAWN'"
EXTRACTION_STATUSES = "'PENDING','EXTRACTED','FAILED','CONFIRMED'"


def upgrade():
    op.drop_constraint("ck_supervisor_requests_title_nonblank", "supervisor_requests", type_="check")
    op.drop_constraint("ck_supervisor_requests_summary_nonblank", "supervisor_requests", type_="check")
    op.alter_column("supervisor_requests", "title", existing_type=sa.String(length=200), nullable=True)
    op.alter_column("supervisor_requests", "summary", existing_type=sa.Text(), nullable=True)
    op.add_column("supervisor_requests", sa.Column("document_id", sa.Integer(), nullable=True))
    op.add_column("supervisor_requests", sa.Column("extraction_status", sa.String(length=16), server_default="PENDING", nullable=False))
    op.add_column("supervisor_requests", sa.Column("extraction_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("supervisor_requests", sa.Column("extraction_confirmed_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_supervisor_requests_extraction_confirmed_by", "supervisor_requests", "users", ["extraction_confirmed_by_id"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("ck_supervisor_requests_title_nonblank", "supervisor_requests", "title IS NULL OR (title = btrim(title) AND title <> '')")
    op.create_check_constraint("ck_supervisor_requests_summary_nonblank", "supervisor_requests", "summary IS NULL OR (summary = btrim(summary) AND summary <> '')")
    op.create_check_constraint("ck_supervisor_requests_extraction_status", "supervisor_requests", f"extraction_status IN ({EXTRACTION_STATUSES})")

    op.create_table(
        "supervisor_request_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("extracted_fields", postgresql.JSONB(), nullable=False),
        sa.Column("extraction_status", sa.String(length=16), nullable=False),
        sa.Column("extraction_runtime", sa.String(length=100), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_supervisor_request_documents_version_positive"),
        sa.CheckConstraint("file_size > 0", name="ck_supervisor_request_documents_file_size_positive"),
        sa.CheckConstraint("page_count = 1", name="ck_supervisor_request_documents_one_page"),
        sa.CheckConstraint(f"extraction_status IN ({EXTRACTION_STATUSES})", name="ck_supervisor_request_documents_extraction_status"),
    )
    op.create_index("uq_supervisor_request_document_version", "supervisor_request_documents", ["request_id", "version"], unique=True)
    op.create_foreign_key("fk_supervisor_requests_document_id", "supervisor_requests", "supervisor_request_documents", ["document_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_supervisor_requests_extraction_status", "supervisor_requests", ["extraction_status"])
    op.execute("CREATE FUNCTION prevent_supervisor_request_document_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'supervisor request documents are immutable'; END $$")
    op.execute("CREATE TRIGGER supervisor_request_document_append_only BEFORE UPDATE OR DELETE ON supervisor_request_documents FOR EACH ROW EXECUTE FUNCTION prevent_supervisor_request_document_mutation()")


def downgrade():
    op.execute("DROP TRIGGER supervisor_request_document_append_only ON supervisor_request_documents")
    op.execute("DROP FUNCTION prevent_supervisor_request_document_mutation()")
    op.drop_index("ix_supervisor_requests_extraction_status", table_name="supervisor_requests")
    op.drop_constraint("fk_supervisor_requests_document_id", "supervisor_requests", type_="foreignkey")
    op.drop_index("uq_supervisor_request_document_version", table_name="supervisor_request_documents")
    op.drop_table("supervisor_request_documents")
    op.drop_constraint("ck_supervisor_requests_extraction_status", "supervisor_requests", type_="check")
    op.drop_constraint("fk_supervisor_requests_extraction_confirmed_by", "supervisor_requests", type_="foreignkey")
    op.drop_column("supervisor_requests", "extraction_confirmed_by_id")
    op.drop_column("supervisor_requests", "extraction_confirmed_at")
    op.drop_column("supervisor_requests", "extraction_status")
    op.drop_column("supervisor_requests", "document_id")
    op.drop_constraint("ck_supervisor_requests_summary_nonblank", "supervisor_requests", type_="check")
    op.drop_constraint("ck_supervisor_requests_title_nonblank", "supervisor_requests", type_="check")
    op.create_check_constraint("ck_supervisor_requests_title_nonblank", "supervisor_requests", "title = btrim(title) AND title <> ''")
    op.create_check_constraint("ck_supervisor_requests_summary_nonblank", "supervisor_requests", "summary = btrim(summary) AND summary <> ''")
    op.alter_column("supervisor_requests", "summary", existing_type=sa.Text(), nullable=False)
    op.alter_column("supervisor_requests", "title", existing_type=sa.String(length=200), nullable=False)
