"""Allow administrators to target all student groups with an announcement."""

from alembic import op


revision = "z7i5d6e7f8g9"
down_revision = "z7h4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_announcements_target_type", "announcements", type_="check")
    op.create_check_constraint(
        "ck_announcements_target_type",
        "announcements",
        "target_type IN ('ALL_USERS','ALL_GROUPS','ROLE','CYCLE','GROUP','PROJECT','ASSIGNED_STUDENTS','ASSIGNED_PANEL')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_announcements_target_type", "announcements", type_="check")
    op.create_check_constraint(
        "ck_announcements_target_type",
        "announcements",
        "target_type IN ('ALL_USERS','ROLE','CYCLE','GROUP','PROJECT','ASSIGNED_STUDENTS','ASSIGNED_PANEL')",
    )
