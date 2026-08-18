"""create payments table

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
        'payments',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_id', sa.Integer, nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(50), server_default='processing', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_payments_order_id', 'payments', ['order_id'])
    op.create_index('ix_payments_status', 'payments', ['status'])


def downgrade() -> None:
    op.drop_index('ix_payments_status', table_name='payments')
    op.drop_index('ix_payments_order_id', table_name='payments')
    op.drop_table('payments')
