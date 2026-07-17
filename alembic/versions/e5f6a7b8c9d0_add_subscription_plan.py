"""add subscription plan and make stripe_customer_id nullable

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-18 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


subscription_plan_enum = postgresql.ENUM('free', 'elite', 'team', name='subscriptionplan', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    subscription_plan_enum.create(bind, checkfirst=True)

    op.add_column(
        'subscriptions',
        sa.Column('plan', subscription_plan_enum, nullable=False, server_default='free'),
    )
    op.alter_column('subscriptions', 'plan', server_default=None)

    # A free plan granted before Stripe keys are configured has no customer yet.
    op.alter_column('subscriptions', 'stripe_customer_id', existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('subscriptions', 'stripe_customer_id', existing_type=sa.String(length=255), nullable=False)
    op.drop_column('subscriptions', 'plan')

    bind = op.get_bind()
    subscription_plan_enum.drop(bind, checkfirst=True)
