"""create orders table

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
        'orders',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('customer_id', sa.Integer, nullable=False),
        sa.Column('product_id', sa.Integer, nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(50), server_default='created', nullable=False),
    )
    op.create_index('ix_orders_customer_id', 'orders', ['customer_id'])
    op.create_index('ix_orders_status', 'orders', ['status'])


def downgrade() -> None:
    op.drop_index('ix_orders_status', table_name='orders')
    op.drop_index('ix_orders_customer_id', table_name='orders')
    op.drop_table('orders')
