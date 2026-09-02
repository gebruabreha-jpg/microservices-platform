"""
Payment Repository Implementation.

Implements PaymentRepository interface using PostgreSQL.
"""

from typing import Callable, List, Dict, Optional, Tuple
from psycopg2 import pool

from shared.interfaces import PaymentRepository
from shared.outbox import enqueue_event

OUTBOX_TABLE = "payment_outbox"


class PostgresPaymentRepository(PaymentRepository):
    """PostgreSQL implementation of PaymentRepository."""

    def __init__(self, db_pool: pool.ThreadedConnectionPool):
        self._db_pool = db_pool

    async def create(
        self,
        payment_data,
        outbox_event: Optional[Callable[[int], Tuple[str, dict]]] = None,
    ) -> int:
        """Create a new payment and return its ID.

        If ``outbox_event`` is given it is called with the new payment id and
        must return ``(topic, payload)``; that event is written to the outbox in
        the same transaction as the payment.
        """
        conn = self._db_pool.getconn()
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO payments (order_id, amount, status) VALUES (%s, %s, %s) RETURNING id",
                (payment_data.order_id, payment_data.amount, payment_data.status),
            )
            payment_id = cur.fetchone()[0]
            if outbox_event is not None:
                topic, payload = outbox_event(payment_id)
                enqueue_event(cur, OUTBOX_TABLE, topic, payload)
            conn.commit()
            return payment_id
        except Exception:
            conn.rollback()
            raise
        finally:
            if cur is not None:
                cur.close()
            self._db_pool.putconn(conn)

    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Get all payments with pagination."""
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, order_id, amount, status, created_at FROM payments ORDER BY id LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "order_id": r[1],
                    "amount": float(r[2]),
                    "status": r[3],
                }
                for r in rows
            ]
        finally:
            cur.close()
            self._db_pool.putconn(conn)

    async def get_by_order_id(self, order_id: int) -> Optional[Dict]:
        """Get payment by order ID (for idempotency checks)."""
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, order_id, amount, status FROM payments WHERE order_id = %s", (order_id,))
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "order_id": row[1],
                    "amount": float(row[2]),
                    "status": row[3],
                }
            return None
        finally:
            cur.close()
            self._db_pool.putconn(conn)
