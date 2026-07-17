"""add response_mode and ratings

Revision ID: c3d4e5f6a7b8
Revises: b7c1f0a9d2e3
Create Date: 2026-07-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b7c1f0a9d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


response_mode_enum = postgresql.ENUM('single_select', 'rate_all', name='responsemodeenum', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    response_mode_enum.create(bind, checkfirst=True)

    op.add_column(
        'assessment_questions',
        sa.Column('response_mode', response_mode_enum, nullable=False, server_default='single_select'),
    )
    op.alter_column('assessment_questions', 'response_mode', server_default=None)

    op.add_column('assessment_responses', sa.Column('rating', sa.Integer(), nullable=True))

    op.drop_constraint('uq_response_session_question', 'assessment_responses', type_='unique')
    op.create_unique_constraint(
        'uq_response_session_question_option', 'assessment_responses', ['session_id', 'question_id', 'option_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_response_session_question_option', 'assessment_responses', type_='unique')
    op.create_unique_constraint(
        'uq_response_session_question', 'assessment_responses', ['session_id', 'question_id'],
    )

    op.drop_column('assessment_responses', 'rating')
    op.drop_column('assessment_questions', 'response_mode')

    bind = op.get_bind()
    response_mode_enum.drop(bind, checkfirst=True)
