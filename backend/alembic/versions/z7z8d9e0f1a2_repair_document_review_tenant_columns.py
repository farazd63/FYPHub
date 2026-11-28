"""Repair tenant columns on generic document-review records."""

from alembic import op


revision = "z7z8d9e0f1a2"
down_revision = "z7z7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The models inherit institution_id from Base, but the original table
    # migration predated that shared tenant column and omitted it.
    for table in (
        "document_review_feedback",
        "document_review_feedback_messages",
        "document_review_annotations",
    ):
        op.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS institution_id INTEGER "
            "REFERENCES institutions(id) ON DELETE SET NULL"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_institution_id "
            f"ON {table} (institution_id)"
        )

    op.execute(
        "UPDATE document_review_feedback feedback "
        "SET institution_id = teams.institution_id "
        "FROM teams "
        "WHERE teams.id = feedback.group_id "
        "AND feedback.institution_id IS NULL"
    )
    op.execute(
        "UPDATE document_review_feedback_messages messages "
        "SET institution_id = feedback.institution_id "
        "FROM document_review_feedback feedback "
        "WHERE feedback.id = messages.feedback_id "
        "AND messages.institution_id IS NULL"
    )
    op.execute(
        "UPDATE document_review_annotations annotations "
        "SET institution_id = teams.institution_id "
        "FROM teams "
        "WHERE teams.id = annotations.group_id "
        "AND annotations.institution_id IS NULL"
    )


def downgrade() -> None:
    for table in (
        "document_review_annotations",
        "document_review_feedback_messages",
        "document_review_feedback",
    ):
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_institution_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS institution_id")
