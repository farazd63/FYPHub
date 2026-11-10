"""Continue the proposal foundation migration chain."""

revision = "fi8d9e0f1a2b"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Converge the already-applied migration branches without changing data."""


def downgrade() -> None:
    """Re-expose the proposal foundation parent for historical downgrades."""
