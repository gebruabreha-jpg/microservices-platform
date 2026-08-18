"""create notifications table

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('order_id', sa.Integer, nullable=False),
        sa.Column('status', sa.String(50), server_default='queued', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_notifications_order_id', 'notifications', ['order_id'])
    op.create_index('ix_notifications_status', 'notifications', ['status'])


def downgrade() -> None:
    op.drop_index('ix_notifications_status', table_name='notifications')
    op.drop_index('ix_notifications_order_id', table_name='notifications')
    op.drop_table('notifications')
