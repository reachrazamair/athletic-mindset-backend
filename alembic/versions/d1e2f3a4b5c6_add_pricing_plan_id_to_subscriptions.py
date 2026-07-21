"""add pricing_plan_id to subscriptions

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-07-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('subscriptions', sa.Column('pricing_plan_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_subscriptions_pricing_plan_id', 'subscriptions', 'pricing_plans', ['pricing_plan_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_subscriptions_pricing_plan_id', 'subscriptions', type_='foreignkey')
    op.drop_column('subscriptions', 'pricing_plan_id')
