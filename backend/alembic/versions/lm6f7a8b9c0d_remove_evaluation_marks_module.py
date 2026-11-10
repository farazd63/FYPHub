"""Remove the retired Evaluation & Marks module.

This migration is intentionally irreversible.  The pre-delete backup is created
outside Alembic so table data can be restored deliberately if required.
"""

from alembic import op


revision = "lm6f7a8b9c0d"
down_revision = "kl5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop children before their parent tables.  IF EXISTS keeps the migration
    # safe for environments where a partial feature deployment created only a
    # subset of the retired tables.
    op.drop_table("panel_evaluation_scores", if_exists=True)
    op.drop_table("panel_evaluations", if_exists=True)
    op.drop_index("ix_evaluation_corrections_evaluation", table_name="evaluation_corrections", if_exists=True)
    op.drop_table("evaluation_corrections", if_exists=True)
    op.drop_index("ix_evaluation_audit_record_created", table_name="evaluation_audit_events", if_exists=True)
    op.drop_table("evaluation_audit_events", if_exists=True)
    op.drop_index("ix_evaluation_records_group", table_name="evaluation_records", if_exists=True)
    op.drop_index("ix_evaluation_records_student", table_name="evaluation_records", if_exists=True)
    op.drop_index("ix_evaluation_records_evaluator", table_name="evaluation_records", if_exists=True)
    op.drop_index("ix_evaluation_records_category_status", table_name="evaluation_records", if_exists=True)
    op.drop_table("evaluation_records", if_exists=True)
    op.drop_table("evaluation_rubric_criteria", if_exists=True)
    op.drop_table("evaluation_rubric_versions", if_exists=True)
    op.drop_table("evaluation_rubrics", if_exists=True)


def downgrade() -> None:
    raise RuntimeError("The Evaluation & Marks removal migration is irreversible; restore from the pre-delete backup instead.")
