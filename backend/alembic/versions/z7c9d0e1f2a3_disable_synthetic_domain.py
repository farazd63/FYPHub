"""Prevent the legacy synthetic group-member domain from being used for signup."""

from alembic import op


revision = "z7c9d0e1f2a3"
down_revision = ("z7b8c9d0e1f2",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE institution_domains SET is_active = FALSE, is_verified = FALSE, "
        "disabled_at = COALESCE(disabled_at, NOW()) WHERE domain = 'group.invalid'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE institution_domains SET is_active = TRUE, is_verified = TRUE, "
        "disabled_at = NULL, verified_at = COALESCE(verified_at, NOW()) WHERE domain = 'group.invalid'"
    )
