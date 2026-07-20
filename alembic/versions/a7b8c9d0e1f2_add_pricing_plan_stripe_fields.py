"""add stripe pricing fields to pricing_plans

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-20 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('pricing_plans', sa.Column('stripe_product_id', sa.String(length=255), nullable=True))
    op.add_column('pricing_plans', sa.Column('monthly_amount_cents', sa.Integer(), nullable=True))
    op.add_column('pricing_plans', sa.Column('yearly_amount_cents', sa.Integer(), nullable=True))
    op.add_column('pricing_plans', sa.Column('stripe_price_id_monthly', sa.String(length=255), nullable=True))
    op.add_column('pricing_plans', sa.Column('stripe_price_id_yearly', sa.String(length=255), nullable=True))
    op.add_column('pricing_plans', sa.Column('currency', sa.String(length=10), nullable=False, server_default='usd'))
    op.alter_column('pricing_plans', 'currency', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('pricing_plans', 'currency')
    op.drop_column('pricing_plans', 'stripe_price_id_yearly')
    op.drop_column('pricing_plans', 'stripe_price_id_monthly')
    op.drop_column('pricing_plans', 'yearly_amount_cents')
    op.drop_column('pricing_plans', 'monthly_amount_cents')
    op.drop_column('pricing_plans', 'stripe_product_id')
