"""add pricing_plans

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-19 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'pricing_plans',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('monthly_price_label', sa.String(length=50), nullable=False),
        sa.Column('monthly_period_label', sa.String(length=50), nullable=False, server_default=''),
        sa.Column('yearly_price_label', sa.String(length=50), nullable=False),
        sa.Column('yearly_period_label', sa.String(length=50), nullable=False, server_default=''),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('locked_features', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('cta_label', sa.String(length=100), nullable=False),
        sa.Column('featured', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.alter_column('pricing_plans', 'monthly_period_label', server_default=None)
    op.alter_column('pricing_plans', 'yearly_period_label', server_default=None)
    op.alter_column('pricing_plans', 'featured', server_default=None)
    op.alter_column('pricing_plans', 'order', server_default=None)
    op.alter_column('pricing_plans', 'is_active', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('pricing_plans')
