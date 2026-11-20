"""Allow multiple named sections in one indexed document version."""

from alembic import op


revision = "v1a2b3c4d5e70"
down_revision = "v1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_group_ai_chunk_scope_source", "group_ai_document_chunks", type_="unique")
    op.create_unique_constraint(
        "uq_group_ai_chunk_scope_source",
        "group_ai_document_chunks",
        ["cycle_id", "group_id", "project_id", "document_id", "version_id", "section_name", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_group_ai_chunk_scope_source", "group_ai_document_chunks", type_="unique")
    op.create_unique_constraint(
        "uq_group_ai_chunk_scope_source",
        "group_ai_document_chunks",
        ["cycle_id", "group_id", "project_id", "document_id", "version_id", "chunk_index"],
    )
