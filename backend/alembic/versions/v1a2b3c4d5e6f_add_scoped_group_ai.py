"""Add cycle/project-scoped group AI chunks and response references."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


revision = "v1a2b3c4d5e6f"
down_revision = "v890a001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "group_messages",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_group_messages_project", "group_messages", ["team_id", "project_id", "channel", "id"])

    op.create_table(
        "group_ai_document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("version_id", sa.String(length=128), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("section_name", sa.String(length=160), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("document_status", sa.String(length=32), nullable=False, server_default="AUTHORIZED"),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "cycle_id", "group_id", "project_id", "document_id", "version_id", "section_name", "chunk_index",
            name="uq_group_ai_chunk_scope_source",
        ),
        sa.CheckConstraint("chunk_index >= 0", name="ck_group_ai_chunk_index_nonnegative"),
    )
    op.create_index("ix_group_ai_chunks_scope", "group_ai_document_chunks", ["cycle_id", "group_id", "project_id"])
    op.create_index("ix_group_ai_chunks_source", "group_ai_document_chunks", ["document_id", "version_id"])
    op.execute("CREATE INDEX ix_group_ai_chunks_embedding_hnsw ON group_ai_document_chunks USING hnsw (embedding vector_cosine_ops)")

    op.create_table(
        "group_ai_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("group_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="CASCADE"), nullable=True),
        sa.Column("response_type", sa.String(length=40), nullable=False, server_default="project"),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("sources", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("used_audit_data", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("used_version_comparison", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("message_id", name="uq_group_ai_response_message"),
    )
    op.create_index("ix_group_ai_responses_scope", "group_ai_responses", ["cycle_id", "group_id", "project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_group_ai_responses_scope", table_name="group_ai_responses")
    op.drop_table("group_ai_responses")
    op.drop_index("ix_group_ai_chunks_source", table_name="group_ai_document_chunks")
    op.drop_index("ix_group_ai_chunks_scope", table_name="group_ai_document_chunks")
    op.execute("DROP INDEX IF EXISTS ix_group_ai_chunks_embedding_hnsw")
    op.drop_table("group_ai_document_chunks")
    op.drop_index("ix_group_messages_project", table_name="group_messages")
    op.drop_column("group_messages", "project_id")
