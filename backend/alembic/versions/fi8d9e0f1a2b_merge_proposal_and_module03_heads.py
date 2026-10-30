"""Merge the proposal-foundation and main application migration branches."""

revision = "fi8d9e0f1a2b"
down_revision = ("c3d4e5f6a7b8", "fh7c8d9e0f1a")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Converge the already-applied migration branches without changing data."""


def downgrade() -> None:
    """Re-expose both parent heads; individual schema downgrades remain separate."""
