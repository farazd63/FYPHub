"""Repair archive storage columns on the active collaboration migration branch."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "rd7e8f9a0b1c"
down_revision = "fc6b7c8d9e0f"
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
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("archived_projects")}
    for item in columns:
        if item[0] in existing:
            continue
        if len(item) == 3:
            name, type_, default = item
            op.add_column("archived_projects", sa.Column(name, type_, nullable=False, server_default=default))
            op.alter_column("archived_projects", name, server_default=None)
        else:
            name, type_ = item
            op.add_column("archived_projects", sa.Column(name, type_, nullable=True))
    if "is_visible_to_students" not in existing:
        op.add_column("archived_projects", sa.Column("is_visible_to_students", sa.Boolean(), nullable=False, server_default=sa.true()))
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("archived_projects")}
    if "ix_archived_projects_cycle_code" not in indexes:
        op.create_index("ix_archived_projects_cycle_code", "archived_projects", ["academic_cycle_id", "project_code"], unique=False)


def downgrade():
    # Shared columns may predate this repair; retain them and their data.
    pass
