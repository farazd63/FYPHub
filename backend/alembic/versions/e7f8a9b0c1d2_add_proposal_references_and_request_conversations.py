"""add authorized proposal references and request conversations"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "proposal_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("normalized_title", sa.String(length=255), nullable=False),
        sa.Column("short_summary", sa.Text(), nullable=False),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("academic_year", sa.String(length=32), nullable=False),
        sa.Column("category_scope", sa.String(length=255), nullable=False),
        sa.Column("source_label", sa.String(length=64), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_proposal_references_normalized_title", "proposal_references", ["normalized_title"])
    op.create_index("ix_proposal_references_cycle_active", "proposal_references", ["academic_cycle_id", "is_active"])
    op.create_table(
        "proposal_reference_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference_id", sa.Integer(), sa.ForeignKey("proposal_references.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("uq_proposal_reference_document_reference", "proposal_reference_documents", ["reference_id"], unique=True)
    op.create_table(
        "supervisor_request_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_supervisor_request_messages_request_id", "supervisor_request_messages", ["request_id", "id"])
    op.execute("CREATE FUNCTION prevent_supervisor_request_message_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'supervisor request messages are append-only'; END $$")
    op.execute("CREATE TRIGGER supervisor_request_message_append_only BEFORE UPDATE OR DELETE ON supervisor_request_messages FOR EACH ROW EXECUTE FUNCTION prevent_supervisor_request_message_mutation()")


def downgrade():
    op.execute("DROP TRIGGER supervisor_request_message_append_only ON supervisor_request_messages")
    op.execute("DROP FUNCTION prevent_supervisor_request_message_mutation()")
    op.drop_index("ix_supervisor_request_messages_request_id", table_name="supervisor_request_messages")
    op.drop_table("supervisor_request_messages")
    op.drop_index("uq_proposal_reference_document_reference", table_name="proposal_reference_documents")
    op.drop_table("proposal_reference_documents")
    op.drop_index("ix_proposal_references_cycle_active", table_name="proposal_references")
    op.drop_index("ix_proposal_references_normalized_title", table_name="proposal_references")
    op.drop_table("proposal_references")
