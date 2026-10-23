"""invitation transactional outbox

Revision ID: a8467cad28da
Revises: eb100aa929ab
Create Date: 2026-10-22 13:55:14.661434

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8467cad28da'
down_revision: Union[str, Sequence[str], None] = 'eb100aa929ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('invitation_outbox',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('invitation_id', sa.Integer(), sa.ForeignKey('team_invitations.id', ondelete='RESTRICT'), nullable=False, unique=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='queued'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('queued', 'smtp_accepted', 'failed', 'unknown')", name='ck_invitation_outbox_status'))
    op.drop_constraint('ck_invitation_audit_action', 'team_invitation_audit', type_='check')
    op.create_check_constraint('ck_invitation_audit_action', 'team_invitation_audit', "action IN ('sent', 'queued', 'accepted', 'rejected')")
    op.execute("INSERT INTO invitation_outbox (invitation_id, status) SELECT id, 'unknown' FROM team_invitations")


def downgrade() -> None:
    op.drop_constraint('ck_invitation_audit_action', 'team_invitation_audit', type_='check')
    op.create_check_constraint('ck_invitation_audit_action', 'team_invitation_audit', "action IN ('sent', 'accepted', 'rejected')")
    op.drop_table('invitation_outbox')
