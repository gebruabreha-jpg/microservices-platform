"""create payment_outbox table

Revision ID: 002
Revises: 001
Create Date: 2026-09-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payment_outbox',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('topic', sa.String(255), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_payment_outbox_unpublished', 'payment_outbox', ['id'],
        postgresql_where=sa.text('published_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_payment_outbox_unpublished', table_name='payment_outbox')
    op.drop_table('payment_outbox')
