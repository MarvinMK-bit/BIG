"""add invalid_mark_pattern to question_results

Revision ID: b93d9441d933
Revises: d2e02d929ff0
Create Date: 2026-09-26 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b93d9441d933'
down_revision: Union[str, None] = 'd2e02d929ff0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('question_results', sa.Column('invalid_mark_pattern', sa.Boolean(), nullable=True))
    # Backfill every result with a breakdown: invalid when a mark is earned after one that was not.
    # A mark is earned when it got its full value, as in app.services.grading.progress.
    op.execute(
        """
        UPDATE question_results AS q
        SET invalid_mark_pattern = EXISTS (
            SELECT 1
            FROM jsonb_array_elements(q.mark_breakdown) WITH ORDINALITY AS lost(item, position)
            JOIN jsonb_array_elements(q.mark_breakdown) WITH ORDINALITY AS later(item, position)
                ON later.position > lost.position
            WHERE (lost.item->>'awarded')::numeric < (lost.item->>'max_mark')::numeric
              AND (later.item->>'awarded')::numeric >= (later.item->>'max_mark')::numeric
        )
        WHERE q.mark_breakdown IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column('question_results', 'invalid_mark_pattern')
