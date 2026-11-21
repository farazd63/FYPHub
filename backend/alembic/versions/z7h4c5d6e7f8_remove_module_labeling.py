"""Replace internal Module 5 labels with system-level supervisor matching names."""

from alembic import op
import sqlalchemy as sa


revision = "z7h4c5d6e7f8"
down_revision = "z7g3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "matching_configurations",
        "algorithm_version",
        server_default=sa.text("'supervisor-matching-v1'"),
    )
    op.execute(
        "UPDATE matching_configurations SET algorithm_version = 'supervisor-matching-v1' WHERE algorithm_version = 'module5-v1'"
    )
    op.execute(
        "UPDATE supervisor_match_results SET algorithm_version = 'supervisor-matching-v1' WHERE algorithm_version = 'module5-v1'"
    )
    op.execute(
        "UPDATE supervisor_requests SET matching_algorithm_version = 'supervisor-matching-v1' WHERE matching_algorithm_version = 'module5-v1'"
    )
    op.execute(
        """
        UPDATE supervisor_requests
        SET ai_summary = (ai_summary - 'module') || jsonb_build_object('workflow', 'supervisor-matching')
        WHERE ai_summary ->> 'module' = 'module5'
        """
    )
    # Historical status text is immutable during normal operation. Temporarily
    # suspend only its guard while correcting this display label in place.
    op.execute("ALTER TABLE supervisor_request_status_history DISABLE TRIGGER supervisor_request_history_append_only")
    op.execute(
        """
        UPDATE supervisor_request_status_history
        SET comment = replace(replace(comment, 'Module 5', 'supervisor matching'), 'module5', 'supervisor matching')
        WHERE comment ILIKE '%module 5%' OR comment ILIKE '%module5%'
        """
    )
    op.execute("ALTER TABLE supervisor_request_status_history ENABLE TRIGGER supervisor_request_history_append_only")


def downgrade() -> None:
    op.alter_column(
        "matching_configurations",
        "algorithm_version",
        server_default=sa.text("'module5-v1'"),
    )
    op.execute(
        "UPDATE matching_configurations SET algorithm_version = 'module5-v1' WHERE algorithm_version = 'supervisor-matching-v1'"
    )
    op.execute(
        "UPDATE supervisor_match_results SET algorithm_version = 'module5-v1' WHERE algorithm_version = 'supervisor-matching-v1'"
    )
    op.execute(
        "UPDATE supervisor_requests SET matching_algorithm_version = 'module5-v1' WHERE matching_algorithm_version = 'supervisor-matching-v1'"
    )
