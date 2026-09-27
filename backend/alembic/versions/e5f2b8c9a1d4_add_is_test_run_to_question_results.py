"""add is_test_run to question_results

Revision ID: e5f2b8c9a1d4
Revises: c4e1a7d3f2b8
Create Date: 2026-09-27 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f2b8c9a1d4'
down_revision: Union[str, None] = 'c4e1a7d3f2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('question_results', sa.Column('is_test_run', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('question_results', 'is_test_run')
