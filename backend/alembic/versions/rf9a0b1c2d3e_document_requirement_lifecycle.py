"""Normalize document requirement lifecycle and bind submissions to groups."""

from alembic import op
import sqlalchemy as sa

revision = "rf9a0b1c2d3e"
down_revision = "re8f9a0b1c2d"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("document_submissions")}
    if "group_id" not in columns:
        op.add_column("document_submissions", sa.Column("group_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True))
    if "academic_cycle_id" not in columns:
        op.add_column("document_submissions", sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=True))
    if "uploaded_by_id" not in columns:
        op.add_column("document_submissions", sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    bind.execute(sa.text("UPDATE document_upload_requirements SET status = 'PUBLISHED' WHERE status = 'ACTIVE'"))
    bind.execute(sa.text("UPDATE document_submissions s SET academic_cycle_id = r.academic_cycle_id, uploaded_by_id = s.student_id, group_id = t.id FROM document_upload_requirements r, teams t WHERE s.requirement_id = r.id AND t.shared_user_id = s.student_id AND s.academic_cycle_id IS NULL"))
    indexes = {item["name"] for item in inspector.get_indexes("document_submissions")}
    if "uq_document_submission_requirement_group" not in indexes:
        op.create_index("uq_document_submission_requirement_group", "document_submissions", ["requirement_id", "group_id"], unique=True, postgresql_where=sa.text("group_id IS NOT NULL"))


def downgrade():
    op.drop_index("uq_document_submission_requirement_group", table_name="document_submissions")
    op.drop_column("document_submissions", "uploaded_by_id")
    op.drop_column("document_submissions", "academic_cycle_id")
    op.drop_column("document_submissions", "group_id")
