"""Add cycle-scoped document archive relationships and review history.

Legacy rows are backfilled only when their cycle, group, section, and project
can be identified from existing records. Rows that remain ambiguous are kept
and placed in an admin review queue.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "sj3e4f5a6b7c"
down_revision = "ri2d3e4f5a6b"
branch_labels = None
depends_on = None


def upgrade():
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
    op.create_index("ix_document_requirement_sections_cycle_order", "document_requirement_sections", ["academic_cycle_id", "display_order"])

    op.add_column("document_upload_requirements", sa.Column("section_id", sa.Integer(), sa.ForeignKey("document_requirement_sections.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("document_submissions", sa.Column("project_id", sa.Integer(), sa.ForeignKey("supervisor_requests.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("document_submissions", sa.Column("requirement_section_id", sa.Integer(), sa.ForeignKey("document_requirement_sections.id", ondelete="RESTRICT"), nullable=True))

    op.create_index("ix_document_requirements_cycle_section", "document_upload_requirements", ["academic_cycle_id", "section_id"])
    op.create_index("ix_document_submissions_archive_scope", "document_submissions", ["academic_cycle_id", "group_id", "project_id"])
    op.create_index("ix_document_submissions_requirement_status", "document_submissions", ["requirement_id", "status"])
    op.create_index("ix_document_submissions_uploaded_at", "document_submissions", ["uploaded_at"])

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
    op.create_index("ix_document_review_events_submission_created", "document_submission_review_events", ["submission_id", "created_at"])
    op.create_index("ix_document_review_events_status", "document_submission_review_events", ["status"])

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
    op.create_index("ix_document_archive_review_queue_status_created", "document_archive_review_queue", ["status", "created_at"])
    op.create_index("ix_document_archive_review_queue_submission", "document_archive_review_queue", ["submission_id"])

    bind = op.get_bind()
    bind.execute(sa.text("""
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
    """))
    bind.execute(sa.text("""
        UPDATE document_upload_requirements r
        SET section_id = s.id
        FROM document_requirement_sections s
        WHERE s.academic_cycle_id = r.academic_cycle_id
          AND s.name = COALESCE(NULLIF(btrim(r.module), ''), 'General')
    """))
    bind.execute(sa.text("""
        UPDATE document_submissions s
        SET academic_cycle_id = r.academic_cycle_id,
            requirement_section_id = r.section_id
        FROM document_upload_requirements r
        WHERE s.requirement_id = r.id
          AND (s.academic_cycle_id IS NULL OR s.requirement_section_id IS NULL)
    """))
    bind.execute(sa.text("""
        UPDATE document_submissions s
        SET group_id = (
            SELECT t.id
            FROM teams t
            JOIN users u ON u.id = s.student_id
            WHERE t.academic_cycle_id = s.academic_cycle_id
              AND t.status <> 'dissolved'
              AND (
                  t.shared_user_id = s.student_id
                  OR EXISTS (
                      SELECT 1 FROM team_members tm
                      WHERE tm.team_id = t.id
                        AND tm.academic_cycle_id = t.academic_cycle_id
                        AND tm.is_active = true
                        AND (tm.registration_number = u.registration_number OR tm.university_email = u.email)
                  )
              )
            ORDER BY t.id
            LIMIT 1
        )
        WHERE s.group_id IS NULL
    """))
    bind.execute(sa.text("""
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
    """))
    bind.execute(sa.text("""
        INSERT INTO document_submission_review_events (submission_id, version_id, status, reviewer_id, comment, created_at)
        SELECT s.id, latest.id, s.status, s.reviewed_by_id, s.review_comment, COALESCE(s.reviewed_at, s.updated_at)
        FROM document_submissions s
        LEFT JOIN LATERAL (
            SELECT v.id FROM document_submission_versions v
            WHERE v.submission_id = s.id
            ORDER BY v.version_number DESC
            LIMIT 1
        ) latest ON true
        WHERE s.reviewed_by_id IS NOT NULL
    """))
    bind.execute(sa.text("""
        INSERT INTO document_archive_review_queue (submission_id, reason, snapshot)
        SELECT s.id,
               'MISSING_ARCHIVE_SCOPE_LINK',
               jsonb_build_object(
                   'submission_id', s.id,
                   'requirement_id', s.requirement_id,
                   'student_id', s.student_id,
                   'cycle_id', s.academic_cycle_id,
                   'group_id', s.group_id,
                   'project_id', s.project_id,
                   'requirement_section_id', s.requirement_section_id
               )
        FROM document_submissions s
        WHERE s.academic_cycle_id IS NULL
           OR s.group_id IS NULL
           OR s.project_id IS NULL
           OR s.requirement_section_id IS NULL
    """))
    op.alter_column("document_upload_requirements", "section_id", nullable=False)


def downgrade():
    op.drop_index("ix_document_archive_review_queue_submission", table_name="document_archive_review_queue")
    op.drop_index("ix_document_archive_review_queue_status_created", table_name="document_archive_review_queue")
    op.drop_table("document_archive_review_queue")
    op.drop_index("ix_document_review_events_status", table_name="document_submission_review_events")
    op.drop_index("ix_document_review_events_submission_created", table_name="document_submission_review_events")
    op.drop_table("document_submission_review_events")
    op.drop_index("ix_document_submissions_uploaded_at", table_name="document_submissions")
    op.drop_index("ix_document_submissions_requirement_status", table_name="document_submissions")
    op.drop_index("ix_document_submissions_archive_scope", table_name="document_submissions")
    op.drop_index("ix_document_requirements_cycle_section", table_name="document_upload_requirements")
    op.drop_column("document_submissions", "requirement_section_id")
    op.drop_column("document_submissions", "project_id")
    op.drop_column("document_upload_requirements", "section_id")
    op.drop_index("ix_document_requirement_sections_cycle_order", table_name="document_requirement_sections")
    op.drop_table("document_requirement_sections")
