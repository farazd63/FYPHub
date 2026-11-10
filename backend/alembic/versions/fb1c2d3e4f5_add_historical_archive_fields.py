"""add structured historical project archive fields"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "fb1c2d3e4f5"
down_revision = "fb1c2d3e4f5a"
branch_labels = None
depends_on = None


def upgrade():
    columns = [
        ("project_code", sa.String(length=120)), ("group_leader_name", sa.String(length=255)),
        ("group_leader_registration_number", sa.String(length=120)), ("group_members", postgresql.JSONB(), sa.text("'[]'::jsonb")),
        ("supervisor_name", sa.String(length=255)), ("session_name", sa.String(length=16)),
        ("problem_statement", sa.Text()), ("objectives", sa.Text()), ("methodology", sa.Text()),
        ("technologies_used", sa.Text()), ("main_features", sa.Text()), ("project_status", sa.String(length=100)),
        ("completion_percentage", sa.Integer()), ("outcomes_results", sa.Text()), ("repository_url", sa.String(length=1000)),
        ("report_url", sa.String(length=1000)), ("presentation_url", sa.String(length=1000)),
        ("external_reference", sa.String(length=1000)), ("notes", sa.Text()),
    ]
    for item in columns:
        if len(item) == 3:
            name, type_, default = item
            op.add_column("archived_projects", sa.Column(name, type_, nullable=False, server_default=default))
            op.alter_column("archived_projects", name, server_default=None)
        else:
            name, type_ = item
            op.add_column("archived_projects", sa.Column(name, type_, nullable=True))
    op.add_column("archived_projects", sa.Column("is_visible_to_students", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_archived_projects_cycle_code", "archived_projects", ["academic_cycle_id", "project_code"], unique=False)


def downgrade():
    op.drop_index("ix_archived_projects_cycle_code", table_name="archived_projects")
    for name in ("is_visible_to_students", "notes", "external_reference", "presentation_url", "report_url", "repository_url", "outcomes_results", "completion_percentage", "project_status", "main_features", "technologies_used", "methodology", "objectives", "problem_statement", "session_name", "supervisor_name", "group_members", "group_leader_registration_number", "group_leader_name", "project_code"):
        op.drop_column("archived_projects", name)
