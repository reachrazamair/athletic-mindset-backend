"""add pending price notice fields to subscriptions

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('subscriptions', sa.Column('pending_price_notice', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('subscriptions', sa.Column('pending_monthly_amount_cents', sa.Integer(), nullable=True))
    op.add_column('subscriptions', sa.Column('pending_yearly_amount_cents', sa.Integer(), nullable=True))
    op.alter_column('subscriptions', 'pending_price_notice', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('subscriptions', 'pending_yearly_amount_cents')
    op.drop_column('subscriptions', 'pending_monthly_amount_cents')
    op.drop_column('subscriptions', 'pending_price_notice')
