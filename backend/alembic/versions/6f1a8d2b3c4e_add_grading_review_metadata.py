"""Add grading review metadata

Revision ID: 6f1a8d2b3c4e
Revises: 3c479b208b5d
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f1a8d2b3c4e'
down_revision: Union[str, Sequence[str], None] = '3c479b208b5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('answers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('manual_review_required', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('grading_method', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('fallback_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ocr_confidence', sa.DECIMAL(4, 3), nullable=True))

    with op.batch_alter_table('answers', schema=None) as batch_op:
        batch_op.alter_column('manual_review_required', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('answers', schema=None) as batch_op:
        batch_op.drop_column('ocr_confidence')
        batch_op.drop_column('fallback_reason')
        batch_op.drop_column('grading_method')
        batch_op.drop_column('manual_review_required')
