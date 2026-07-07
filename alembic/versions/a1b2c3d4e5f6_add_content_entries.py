"""add content_entries

Revision ID: a1b2c3d4e5f6
Revises: e87032e7ea6a
Create Date: 2026-07-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e87032e7ea6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'content_entries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('locale', sa.String(length=10), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', 'locale', name='uq_content_key_locale'),
    )
    op.create_index(op.f('ix_content_entries_key'), 'content_entries', ['key'], unique=False)
    op.create_index(op.f('ix_content_entries_locale'), 'content_entries', ['locale'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_content_entries_locale'), table_name='content_entries')
    op.drop_index(op.f('ix_content_entries_key'), table_name='content_entries')
    op.drop_table('content_entries')
