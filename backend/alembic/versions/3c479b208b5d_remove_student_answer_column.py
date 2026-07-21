"""Remove student_answer column

Revision ID: 3c479b208b5d
Revises: 87ac2eb49c84
Create Date: 2026-06-20 04:43:44.522030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '3c479b208b5d'
down_revision: Union[str, Sequence[str], None] = '87ac2eb49c84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _answers_columns():
    return {c['name'] for c in inspect(op.get_bind()).get_columns('answers')}


def upgrade() -> None:
    """Drop the legacy student_answer column if present.

    The initial migration (and current models) never define student_answer, so
    on a fresh DB there is nothing to drop — guard the drop so `alembic upgrade
    head` doesn't fail. Legacy DBs created from the old raw SQL schema may still
    have the column, and it is removed there.
    """
    if 'student_answer' in _answers_columns():
        with op.batch_alter_table('answers', schema=None) as batch_op:
            batch_op.drop_column('student_answer')


def downgrade() -> None:
    """Re-add student_answer only if it isn't already present."""
    if 'student_answer' not in _answers_columns():
        with op.batch_alter_table('answers', schema=None) as batch_op:
            batch_op.add_column(sa.Column('student_answer', sa.TEXT(), nullable=True))
