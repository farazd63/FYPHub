"""Add approved student roster and import provenance."""
from alembic import op
import sqlalchemy as sa
revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("roster_imports", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False), sa.Column("imported_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("confirmation_hash", sa.String(64), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.create_table("approved_students", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False), sa.Column("import_id", sa.Integer(), sa.ForeignKey("roster_imports.id", ondelete="RESTRICT"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("registration_number", sa.String(100), nullable=False), sa.Column("university_email", sa.String(320), nullable=False), sa.Column("semester", sa.Integer(), nullable=False), sa.Column("group_code", sa.String(100), nullable=False), sa.Column("project_topic", sa.Text()), sa.UniqueConstraint("academic_cycle_id", "university_email", name="uq_approved_student_cycle_email"), sa.CheckConstraint("semester IN (7, 8)", name="ck_approved_student_semester"))

    op.create_index("uq_approved_student_cycle_registration", "approved_students", ["academic_cycle_id", sa.text("lower(registration_number)")], unique=True)

def downgrade():
    op.drop_table("approved_students")
    op.drop_table("roster_imports")
