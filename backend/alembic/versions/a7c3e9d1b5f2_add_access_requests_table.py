"""add access_requests table

Revision ID: a7c3e9d1b5f2
Revises: 59abacaf25fd
Create Date: 2026-10-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e9d1b5f2'
down_revision: Union[str, None] = '59abacaf25fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('access_requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('username', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('display_name', sa.String(), nullable=True),
    sa.Column('about', sa.Text(), nullable=False),
    sa.Column('password_hash', sa.String(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'DECLINED', name='access_request_status'), nullable=False),
    sa.Column('reviewed_by_id', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('email IS NOT NULL OR phone IS NOT NULL', name='ck_access_requests_contact'),
    sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_access_requests_status'), 'access_requests', ['status'], unique=False)
    op.create_index(op.f('ix_access_requests_username'), 'access_requests', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_access_requests_username'), table_name='access_requests')
    op.drop_index(op.f('ix_access_requests_status'), table_name='access_requests')
    op.drop_table('access_requests')
    sa.Enum(name='access_request_status').drop(op.get_bind(), checkfirst=True)
