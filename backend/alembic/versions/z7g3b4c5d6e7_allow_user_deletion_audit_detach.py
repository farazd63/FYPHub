"""Allow permanently deleted users to detach from audit targets."""

from alembic import op


revision = "z7g3b4c5d6e7"
down_revision = "z7f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "admin_audit_events_affected_user_id_fkey",
        "admin_audit_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "admin_audit_events_affected_user_id_fkey",
        "admin_audit_events",
        "users",
        ["affected_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "admin_audit_events_affected_user_id_fkey",
        "admin_audit_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "admin_audit_events_affected_user_id_fkey",
        "admin_audit_events",
        "users",
        ["affected_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
