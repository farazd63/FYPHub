"""Remove registry, roster, workflow-draft, invitation and identity modules.

The removed features were explicitly retired.  This migration intentionally
deletes their persisted records and tables while leaving users, teams,
academic cycles, proposals, documents and other active workflows intact.
"""

from alembic import op


revision = "r678a001"
down_revision = "p567a001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TeamMember.student_id was only a foreign key into the retired approved
    # roster.  Keep the member contact fields and remove that association first.
    op.execute("ALTER TABLE team_members DROP COLUMN IF EXISTS student_id CASCADE")

    # Drop dependent match/chat records before their parent tables.
    for table in (
        "module2_match_reports",
        "match_chat_consents",
        "match_messages",
        "match_chats",
        "team_match_preferences",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    # Identity, invitation, join-request and roster data is no longer part of
    # the application and may be removed safely as requested.
    for table in (
        "anonymous_identity_proofs",
        "anonymous_verification_challenges",
        "anonymous_verification_contexts",
        "identity_proofs",
        "identity_challenges",
        "team_invitation_audit",
        "invitation_outbox",
        "team_invitations",
        "join_request_audit",
        "join_requests",
        "approved_students",
        "roster_imports",
        "fyp_registry_metadata",
        "workflow_policy_versions",
        "workflow_policies",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def downgrade() -> None:
    raise NotImplementedError("The retired registry, roster and identity data cannot be restored.")
