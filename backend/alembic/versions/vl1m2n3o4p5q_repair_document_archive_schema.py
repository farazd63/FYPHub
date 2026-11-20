"""Repair document archive schema when head was stamped without applying sj3e.

Idempotent: safe on DBs that already have the archive tables/columns and on
DBs that were stamped past sj3e4f5a6b7c / tk4f5a6b7c8d without running them.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "vl1m2n3o4p5q"
down_revision = "sj3k4l5m6n7o"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return bind.execute(sa.text("SELECT to_regclass(:name) IS NOT NULL"), {"name": f"public.{name}"}).scalar()


def _has_column(bind, table: str, column: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table AND column_name = :column
                """
            ),
            {"table": table, "column": column},
        ).scalar()
    )


def _has_index(bind, name: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :name"),
            {"name": name},
        ).scalar()
    )


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "document_requirement_sections"):
        op.create_table(
            "document_requirement_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("academic_cycle_id", "code", name="uq_document_requirement_section_cycle_code"),
        )
    if not _has_index(bind, "ix_document_requirement_sections_cycle_order"):
        op.create_index(
            "ix_document_requirement_sections_cycle_order",
            "document_requirement_sections",
            ["academic_cycle_id", "display_order"],
        )

    if not _has_column(bind, "document_upload_requirements", "section_id"):
        op.add_column(
            "document_upload_requirements",
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("document_requirement_sections.id", ondelete="RESTRICT"), nullable=True),
        )
    if not _has_column(bind, "document_submissions", "project_id"):
        op.add_column(
            "document_submissions",
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=True),
        )
    if not _has_column(bind, "document_submissions", "requirement_section_id"):
        op.add_column(
            "document_submissions",
            sa.Column(
                "requirement_section_id",
                sa.Integer(),
                sa.ForeignKey("document_requirement_sections.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )

    if not _has_index(bind, "ix_document_requirements_cycle_section"):
        op.create_index(
            "ix_document_requirements_cycle_section",
            "document_upload_requirements",
            ["academic_cycle_id", "section_id"],
        )
    if not _has_index(bind, "ix_document_submissions_archive_scope"):
        op.create_index(
            "ix_document_submissions_archive_scope",
            "document_submissions",
            ["academic_cycle_id", "group_id", "project_id"],
        )
    if not _has_index(bind, "ix_document_submissions_requirement_status"):
        op.create_index(
            "ix_document_submissions_requirement_status",
            "document_submissions",
            ["requirement_id", "status"],
        )
    if not _has_index(bind, "ix_document_submissions_uploaded_at"):
        op.create_index("ix_document_submissions_uploaded_at", "document_submissions", ["uploaded_at"])

    if not _has_table(bind, "document_submission_review_events"):
        op.create_table(
            "document_submission_review_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("submission_id", sa.Integer(), sa.ForeignKey("document_submissions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_id", sa.Integer(), sa.ForeignKey("document_submission_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    if not _has_index(bind, "ix_document_review_events_submission_created"):
        op.create_index(
            "ix_document_review_events_submission_created",
            "document_submission_review_events",
            ["submission_id", "created_at"],
        )
    if not _has_index(bind, "ix_document_review_events_status"):
        op.create_index("ix_document_review_events_status", "document_submission_review_events", ["status"])

    if not _has_table(bind, "document_archive_review_queue"):
        op.create_table(
            "document_archive_review_queue",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("submission_id", sa.Integer(), sa.ForeignKey("document_submissions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reason", sa.String(120), nullable=False),
            sa.Column("snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("status", sa.String(24), nullable=False, server_default="OPEN"),
            sa.Column("resolved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    if not _has_index(bind, "ix_document_archive_review_queue_status_created"):
        op.create_index(
            "ix_document_archive_review_queue_status_created",
            "document_archive_review_queue",
            ["status", "created_at"],
        )
    if not _has_index(bind, "ix_document_archive_review_queue_submission"):
        op.create_index(
            "ix_document_archive_review_queue_submission",
            "document_archive_review_queue",
            ["submission_id"],
        )

    if not _has_column(bind, "teams", "group_number"):
        op.add_column("teams", sa.Column("group_number", sa.Integer(), nullable=True))
        bind.execute(
            sa.text(
                """
                UPDATE teams AS target
                SET group_number = numbered.group_number
                FROM (
                    SELECT id, row_number() OVER (PARTITION BY academic_cycle_id ORDER BY created_at, id) AS group_number
                    FROM teams
                ) AS numbered
                WHERE target.id = numbered.id
                """
            )
        )
        op.create_unique_constraint("uq_teams_cycle_group_number", "teams", ["academic_cycle_id", "group_number"])
        op.create_check_constraint("ck_teams_group_number_positive", "teams", "group_number IS NULL OR group_number > 0")

    # Backfill sections + links (safe to re-run; inserts skip existing section codes).
    bind.execute(
        sa.text(
            """
            WITH modules AS (
                SELECT DISTINCT academic_cycle_id, COALESCE(NULLIF(btrim(module), ''), 'General') AS name
                FROM document_upload_requirements
            ), numbered AS (
                SELECT academic_cycle_id, name,
                       lower(regexp_replace(name, '[^a-zA-Z0-9]+', '_', 'g')) AS code,
                       row_number() OVER (PARTITION BY academic_cycle_id ORDER BY name) - 1 AS display_order
                FROM modules
            )
            INSERT INTO document_requirement_sections (academic_cycle_id, code, name, display_order)
            SELECT academic_cycle_id, COALESCE(NULLIF(code, ''), 'general'), name, display_order
            FROM numbered
            ON CONFLICT (academic_cycle_id, code) DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE document_upload_requirements r
            SET section_id = s.id
            FROM document_requirement_sections s
            WHERE r.section_id IS NULL
              AND s.academic_cycle_id = r.academic_cycle_id
              AND s.name = COALESCE(NULLIF(btrim(r.module), ''), 'General')
            """
        )
    )
    # Ensure every requirement has a section (create General per cycle if needed).
    bind.execute(
        sa.text(
            """
            INSERT INTO document_requirement_sections (academic_cycle_id, code, name, display_order)
            SELECT DISTINCT r.academic_cycle_id, 'general', 'General', 0
            FROM document_upload_requirements r
            WHERE r.section_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM document_requirement_sections s
                  WHERE s.academic_cycle_id = r.academic_cycle_id AND s.code = 'general'
              )
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE document_upload_requirements r
            SET section_id = s.id
            FROM document_requirement_sections s
            WHERE r.section_id IS NULL
              AND s.academic_cycle_id = r.academic_cycle_id
              AND s.code = 'general'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE document_submissions s
            SET academic_cycle_id = r.academic_cycle_id,
                requirement_section_id = r.section_id
            FROM document_upload_requirements r
            WHERE s.requirement_id = r.id
              AND (s.academic_cycle_id IS NULL OR s.requirement_section_id IS NULL)
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE document_submissions s
            SET project_id = (
                SELECT sr.id
                FROM supervisor_requests sr
                WHERE sr.team_id = s.group_id
                  AND sr.academic_cycle_id = s.academic_cycle_id
                  AND sr.status NOT IN ('WITHDRAWN', 'REJECTED')
                ORDER BY sr.updated_at DESC, sr.id DESC
                LIMIT 1
            )
            WHERE s.project_id IS NULL AND s.group_id IS NOT NULL
            """
        )
    )

    # Only tighten NOT NULL once every requirement row has a section.
    orphan = bind.execute(sa.text("SELECT COUNT(*) FROM document_upload_requirements WHERE section_id IS NULL")).scalar()
    if orphan == 0:
        op.alter_column("document_upload_requirements", "section_id", nullable=False)


def downgrade() -> None:
    # Non-destructive repair; leave schema in place.
    pass
