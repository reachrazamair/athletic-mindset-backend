"""add coach referrals

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-07-23 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('referral_code', sa.String(length=16), nullable=True))
    op.create_unique_constraint('uq_users_referral_code', 'users', ['referral_code'])
    op.add_column('users', sa.Column('pending_referral_code', sa.String(length=16), nullable=True))

    op.create_table(
        'coach_referrals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('coach_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('athlete_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('referral_code', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['coach_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['athlete_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('athlete_user_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('coach_referrals')
    op.drop_column('users', 'pending_referral_code')
    op.drop_constraint('uq_users_referral_code', 'users', type_='unique')
    op.drop_column('users', 'referral_code')
