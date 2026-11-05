"""Repair Module 1 evaluation tables after removing the retired compliance branch.

The project kept the evaluation models and routes after the temporary module
removal. Some local databases therefore reached the latest Alembic revision
without the tables that the active models still require. These idempotent
statements repair that drift without deleting existing data.
"""

from alembic import op


revision = "oa1b2c3d4e5f"
down_revision = "mo8r9e0f1a2b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluation_rubrics (
            id INTEGER PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluation_rubric_versions (
            id INTEGER PRIMARY KEY,
            rubric_id INTEGER NOT NULL REFERENCES evaluation_rubrics(id) ON DELETE RESTRICT,
            version_number INTEGER NOT NULL,
            name VARCHAR(160) NOT NULL,
            description TEXT,
            created_by_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_evaluation_rubric_version UNIQUE (rubric_id, version_number)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluation_rubric_criteria (
            id INTEGER PRIMARY KEY,
            rubric_version_id INTEGER NOT NULL REFERENCES evaluation_rubric_versions(id) ON DELETE RESTRICT,
            name VARCHAR(160) NOT NULL,
            description TEXT,
            display_order INTEGER NOT NULL,
            CONSTRAINT uq_evaluation_rubric_criterion_order UNIQUE (rubric_version_id, display_order)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS panel_evaluations (
            id INTEGER PRIMARY KEY,
            schedule_id INTEGER NOT NULL REFERENCES defense_schedules(id) ON DELETE RESTRICT,
            evaluator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            status VARCHAR(24) NOT NULL DEFAULT 'DRAFT',
            overall_score INTEGER,
            overall_feedback TEXT,
            decision VARCHAR(64),
            disagreement_detected BOOLEAN NOT NULL DEFAULT false,
            resolution_note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_panel_evaluation_schedule_evaluator UNIQUE (schedule_id, evaluator_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS panel_evaluation_scores (
            id INTEGER PRIMARY KEY,
            evaluation_id INTEGER NOT NULL REFERENCES panel_evaluations(id) ON DELETE CASCADE,
            criterion_key VARCHAR(160) NOT NULL,
            score INTEGER NOT NULL,
            max_score INTEGER NOT NULL,
            feedback TEXT,
            CONSTRAINT uq_panel_evaluation_score_criterion UNIQUE (evaluation_id, criterion_key)
        )
        """
    )


def downgrade() -> None:
    # This repair migration is intentionally non-destructive. The tables may
    # have existed before the repair and may contain live evaluation data.
    pass
