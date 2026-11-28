"""Add version-scoped review records for generic requirements."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "z7z7c8d9e0f1"
down_revision = "z7z6b7c8d9e0"
branch_labels = None
depends_on = None


def _json_default():
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "document_review_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("marker_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("feedback_level", sa.String(length=24), nullable=False, server_default="FULL_DOCUMENT"),
        sa.Column("feedback_type", sa.String(length=32), nullable=False, server_default="GENERAL_COMMENT"),
        sa.Column("correction_action", sa.String(length=24), nullable=False, server_default="NONE"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=True),
        sa.Column("selected_text", sa.Text(), nullable=True),
        sa.Column("location", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=_json_default()),
        sa.Column("destination_location", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="MEDIUM"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workflow_status", sa.String(length=24), nullable=False, server_default="OPEN"),
        sa.Column("publication_status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["submission_id"], ["document_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["document_submission_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_document_review_feedback_submission", "document_review_feedback", ["submission_id", "created_at"])
    op.create_index("ix_document_review_feedback_version", "document_review_feedback", ["version_id", "publication_status"])
    op.create_index("ix_document_review_feedback_group", "document_review_feedback", ["group_id", "publication_status"])

    op.create_table(
        "document_review_feedback_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feedback_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["feedback_id"], ["document_review_feedback.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_document_review_feedback_messages_feedback_created", "document_review_feedback_messages", ["feedback_id", "created_at"])

    op.create_table(
        "document_review_annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("annotation_type", sa.String(length=32), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=_json_default()),
        sa.Column("drawing", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=_json_default()),
        sa.Column("selected_text", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("suggested_text", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#F5C542"),
        sa.Column("stroke_width", sa.Float(), nullable=False, server_default="2"),
        sa.Column("publication_status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("feedback_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["submission_id"], ["document_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["document_submission_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["feedback_id"], ["document_review_feedback.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_document_review_annotations_submission_page", "document_review_annotations", ["submission_id", "version_id", "page_number"])
    op.create_index("ix_document_review_annotations_group_status", "document_review_annotations", ["group_id", "publication_status"])


def downgrade() -> None:
    op.drop_index("ix_document_review_annotations_group_status", table_name="document_review_annotations")
    op.drop_index("ix_document_review_annotations_submission_page", table_name="document_review_annotations")
    op.drop_table("document_review_annotations")
    op.drop_index("ix_document_review_feedback_messages_feedback_created", table_name="document_review_feedback_messages")
    op.drop_table("document_review_feedback_messages")
    op.drop_index("ix_document_review_feedback_group", table_name="document_review_feedback")
    op.drop_index("ix_document_review_feedback_version", table_name="document_review_feedback")
    op.drop_index("ix_document_review_feedback_submission", table_name="document_review_feedback")
    op.drop_table("document_review_feedback")
