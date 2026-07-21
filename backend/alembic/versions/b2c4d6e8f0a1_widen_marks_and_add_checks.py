"""Widen marks DECIMAL columns and add value-range checks

DECIMAL(5,2) caps at 999.99, which a scaled total or a many-question paper can
overflow. Widen the money/marks columns to DECIMAL(7,2) and add CHECK constraints
so marks can't go negative and similarity_score stays within [0, 1].

Revision ID: b2c4d6e8f0a1
Revises: 6f1a8d2b3c4e
Create Date: 2026-06-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c4d6e8f0a1'
down_revision: Union[str, Sequence[str], None] = '6f1a8d2b3c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_WIDE = sa.DECIMAL(precision=7, scale=2)
_NARROW = sa.DECIMAL(precision=5, scale=2)


def upgrade() -> None:
    with op.batch_alter_table('submissions', schema=None) as batch_op:
        batch_op.alter_column('total_marks', existing_type=_NARROW, type_=_WIDE)
        batch_op.alter_column('max_total_marks', existing_type=_NARROW, type_=_WIDE)

    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.alter_column('total_marks', existing_type=_NARROW, type_=_WIDE)

    with op.batch_alter_table('assessment_questions', schema=None) as batch_op:
        batch_op.alter_column('max_marks', existing_type=_NARROW, type_=_WIDE)

    with op.batch_alter_table('answers', schema=None) as batch_op:
        batch_op.alter_column('marks_obtained', existing_type=_NARROW, type_=_WIDE)
        batch_op.alter_column('max_marks', existing_type=_NARROW, type_=_WIDE)
        batch_op.create_check_constraint('ck_answers_marks_nonneg', 'marks_obtained >= 0')
        batch_op.create_check_constraint('ck_answers_max_marks_nonneg', 'max_marks >= 0')
        batch_op.create_check_constraint(
            'ck_answers_similarity_range',
            'similarity_score IS NULL OR (similarity_score >= 0 AND similarity_score <= 1)',
        )


def downgrade() -> None:
    with op.batch_alter_table('answers', schema=None) as batch_op:
        batch_op.drop_constraint('ck_answers_similarity_range', type_='check')
        batch_op.drop_constraint('ck_answers_max_marks_nonneg', type_='check')
        batch_op.drop_constraint('ck_answers_marks_nonneg', type_='check')
        batch_op.alter_column('marks_obtained', existing_type=_WIDE, type_=_NARROW)
        batch_op.alter_column('max_marks', existing_type=_WIDE, type_=_NARROW)

    with op.batch_alter_table('assessment_questions', schema=None) as batch_op:
        batch_op.alter_column('max_marks', existing_type=_WIDE, type_=_NARROW)

    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.alter_column('total_marks', existing_type=_WIDE, type_=_NARROW)

    with op.batch_alter_table('submissions', schema=None) as batch_op:
        batch_op.alter_column('total_marks', existing_type=_WIDE, type_=_NARROW)
        batch_op.alter_column('max_total_marks', existing_type=_WIDE, type_=_NARROW)
