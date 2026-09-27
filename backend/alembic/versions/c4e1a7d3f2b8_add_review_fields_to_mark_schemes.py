"""add review fields to mark_schemes

Revision ID: c4e1a7d3f2b8
Revises: b93d9441d933
Create Date: 2026-09-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4e1a7d3f2b8'
down_revision: Union[str, None] = 'b93d9441d933'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

review_status = sa.Enum('PENDING', 'ACCEPTED', 'DECLINED', name='scheme_review_status')


def upgrade() -> None:
    review_status.create(op.get_bind(), checkfirst=True)
    # The server default makes every existing scheme PENDING
    op.add_column(
        'mark_schemes',
        sa.Column('review_status', review_status, server_default='PENDING', nullable=False),
    )
    op.add_column('mark_schemes', sa.Column('reviewed_by_id', sa.UUID(), nullable=True))
    op.add_column('mark_schemes', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('mark_schemes', sa.Column('review_note', sa.Text(), nullable=True))
    op.add_column('mark_schemes', sa.Column('exported_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        'fk_mark_schemes_reviewed_by_id_users', 'mark_schemes', 'users', ['reviewed_by_id'], ['id']
    )
    op.create_index(op.f('ix_mark_schemes_review_status'), 'mark_schemes', ['review_status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mark_schemes_review_status'), table_name='mark_schemes')
    op.drop_constraint('fk_mark_schemes_reviewed_by_id_users', 'mark_schemes', type_='foreignkey')
    op.drop_column('mark_schemes', 'exported_at')
    op.drop_column('mark_schemes', 'review_note')
    op.drop_column('mark_schemes', 'reviewed_at')
    op.drop_column('mark_schemes', 'reviewed_by_id')
    op.drop_column('mark_schemes', 'review_status')
    review_status.drop(op.get_bind(), checkfirst=True)
