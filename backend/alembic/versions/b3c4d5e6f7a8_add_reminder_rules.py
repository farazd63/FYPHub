"""Add non-operational reminder rule versions."""
from alembic import op
import sqlalchemy as sa
revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("reminder_rules", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("academic_cycle_id", sa.Integer(), sa.ForeignKey("academic_cycles.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.create_table("reminder_rule_versions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("rule_id", sa.Integer(), sa.ForeignKey("reminder_rules.id", ondelete="RESTRICT"), nullable=False), sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("deadline_version_id", sa.Integer(), sa.ForeignKey("academic_deadline_versions.id", ondelete="RESTRICT"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text()), sa.Column("category", sa.String(16), nullable=False), sa.Column("direction", sa.String(6), nullable=False), sa.Column("elapsed_minutes", sa.Integer(), nullable=False), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.UniqueConstraint("rule_id", "version_number", name="uq_reminder_rule_version"), sa.CheckConstraint("elapsed_minutes > 0", name="ck_reminder_rule_minutes"), sa.CheckConstraint("category IN ('REMINDER', 'ESCALATION')", name="ck_reminder_rule_category"), sa.CheckConstraint("direction IN ('BEFORE', 'AFTER')", name="ck_reminder_rule_direction"))

def downgrade():
    op.drop_table("reminder_rule_versions")
    op.drop_table("reminder_rules")
