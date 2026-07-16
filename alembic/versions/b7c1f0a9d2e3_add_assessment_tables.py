"""add assessment tables

Revision ID: b7c1f0a9d2e3
Revises: a1b2c3d4e5f6
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7c1f0a9d2e3'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# create_type=False: the enum types are created explicitly (once, checkfirst)
# in upgrade() below, so the column definitions must not try to create them again.
question_type_enum = postgresql.ENUM('likert', 'scenario', name='questiontypeenum', create_type=False)
measurement_type_enum = postgresql.ENUM('trait', 'state', name='measurementtypeenum', create_type=False)
question_tier_enum = postgresql.ENUM('free', 'elite', name='questiontierenum', create_type=False)
sport_category_enum = postgresql.ENUM('team', 'individual', 'combat', name='sportcategoryenum', create_type=False)
session_status_enum = postgresql.ENUM('in_progress', 'completed', name='assessmentsessionstatus', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    question_type_enum.create(bind, checkfirst=True)
    measurement_type_enum.create(bind, checkfirst=True)
    question_tier_enum.create(bind, checkfirst=True)
    sport_category_enum.create(bind, checkfirst=True)
    session_status_enum.create(bind, checkfirst=True)

    op.create_table(
        'assessment_phases',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )

    op.create_table(
        'assessment_factors',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('phase_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['phase_id'], ['assessment_phases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phase_id', 'key', name='uq_factor_phase_key'),
    )

    op.create_table(
        'assessment_dimensions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('factor_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['factor_id'], ['assessment_factors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('factor_id', 'key', name='uq_dimension_factor_key'),
    )

    op.create_table(
        'assessment_questions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('dimension_id', sa.UUID(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('helper_text', sa.Text(), nullable=True),
        sa.Column('question_type', question_type_enum, nullable=False),
        sa.Column('measurement_type', measurement_type_enum, nullable=False),
        sa.Column('tier', question_tier_enum, nullable=False),
        sa.Column('reverse_scored', sa.Boolean(), nullable=False),
        sa.Column('sport_category_overrides', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('position_overrides', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dimension_id'], ['assessment_dimensions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'assessment_question_options',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('label', sa.String(length=1), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('tag', sa.String(length=100), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['assessment_questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_id', 'label', name='uq_option_question_label'),
    )

    # Team / Individual / Combat — entered by the athlete as part of the
    # assessment's own registration step, stored on their profile.
    op.add_column('athlete_profiles', sa.Column('sport_category', sport_category_enum, nullable=True))

    op.create_table(
        'assessment_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('tier', question_tier_enum, nullable=False),
        sa.Column('status', session_status_enum, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'assessment_responses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('option_id', sa.UUID(), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['assessment_questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['option_id'], ['assessment_question_options.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'question_id', name='uq_response_session_question'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('assessment_responses')
    op.drop_table('assessment_sessions')
    op.drop_column('athlete_profiles', 'sport_category')
    op.drop_table('assessment_question_options')
    op.drop_table('assessment_questions')
    op.drop_table('assessment_dimensions')
    op.drop_table('assessment_factors')
    op.drop_table('assessment_phases')

    bind = op.get_bind()
    session_status_enum.drop(bind, checkfirst=True)
    sport_category_enum.drop(bind, checkfirst=True)
    question_tier_enum.drop(bind, checkfirst=True)
    measurement_type_enum.drop(bind, checkfirst=True)
    question_type_enum.drop(bind, checkfirst=True)
