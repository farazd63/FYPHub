"""Store current supervisor profile facts and shared document metadata."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector


revision = "aa8b9c0d1e2f"
down_revision = "z7o8p9q0r1s2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supervisor_profiles", sa.Column("degree", sa.String(255), nullable=True))
    op.add_column("supervisor_profiles", sa.Column("specialization", sa.String(255), nullable=True))
    op.add_column("supervisor_profiles", sa.Column("publications", JSONB(), nullable=False, server_default="[]"))

    op.add_column("supervised_project_history", sa.Column("source_type", sa.String(32), nullable=False, server_default="LEGACY_MANUAL"))
    op.add_column("supervised_project_history", sa.Column("source_id", sa.Integer(), nullable=True))
    op.create_index("ix_supervised_project_history_source", "supervised_project_history", ["source_type", "source_id"])
    op.alter_column("supervised_project_history", "source_type", server_default="DERIVED")

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_title", sa.String(255), nullable=True),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("access_policy", JSONB(), nullable=False, server_default="{}"),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_type", "source_id", name="uq_knowledge_documents_source"),
    )
    op.create_index("ix_knowledge_documents_institution_id", "knowledge_documents", ["institution_id"])
    op.create_index("ix_knowledge_documents_scope", "knowledge_documents", ["academic_cycle_id", "team_id", "supervisor_id"])
    op.create_index("ix_knowledge_documents_permissions", "knowledge_documents", ["student_user_id", "supervisor_id"])

    op.create_table(
        "knowledge_document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_document_chunk"),
    )
    op.create_index("ix_knowledge_document_chunks_institution_id", "knowledge_document_chunks", ["institution_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_document_chunks_institution_id", table_name="knowledge_document_chunks")
    op.drop_table("knowledge_document_chunks")
    op.drop_index("ix_knowledge_documents_permissions", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_scope", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_institution_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_index("ix_supervised_project_history_source", table_name="supervised_project_history")
    op.drop_column("supervised_project_history", "source_id")
    op.drop_column("supervised_project_history", "source_type")
    op.drop_column("supervisor_profiles", "publications")
    op.drop_column("supervisor_profiles", "specialization")
    op.drop_column("supervisor_profiles", "degree")
