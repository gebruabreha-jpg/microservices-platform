"""
Order Repository Implementation.

Implements OrderRepository interface using PostgreSQL.
"""

from typing import Callable, List, Dict, Optional, Tuple
from psycopg2 import pool

from shared.interfaces import OrderRepository
from shared.outbox import enqueue_event

OUTBOX_TABLE = "order_outbox"


class PostgresOrderRepository(OrderRepository):
    """PostgreSQL implementation of OrderRepository."""

    def __init__(self, db_pool: pool.ThreadedConnectionPool):
        self._db_pool = db_pool

    async def create(
        self,
        order_data,
        outbox_event: Optional[Callable[[int], Tuple[str, dict]]] = None,
    ) -> int:
        """Create a new order and return its ID.

        If ``outbox_event`` is given it is called with the new order id and must
        return ``(topic, payload)``; that event is written to the outbox in the
        same transaction as the order, so it cannot be lost or published early.
        """
        conn = self._db_pool.getconn()
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO orders (customer_id, product_id, quantity, amount, status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (order_data.customer_id, order_data.product_id, order_data.quantity, order_data.amount, order_data.status),
            )
            order_id = cur.fetchone()[0]
            if outbox_event is not None:
                topic, payload = outbox_event(order_id)
                enqueue_event(cur, OUTBOX_TABLE, topic, payload)
            conn.commit()
            return order_id
        except Exception:
            conn.rollback()
            raise
        finally:
            if cur is not None:
                cur.close()
            self._db_pool.putconn(conn)

    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Get all orders with pagination."""
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, customer_id, product_id, quantity, amount, status FROM orders ORDER BY id LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "customer_id": r[1],
                    "product_id": r[2],
                    "quantity": r[3],
                    "amount": float(r[4]),
                    "status": r[5],
                }
                for r in rows
            ]
        finally:
            cur.close()
            self._db_pool.putconn(conn)

    async def get_by_id(self, order_id: int) -> Optional[Dict]:
        """Get a single order by id, or None."""
        conn = self._db_pool.getconn()
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, customer_id, product_id, quantity, amount, status FROM orders WHERE id = %s",
                (order_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "customer_id": row[1],
                "product_id": row[2],
                "quantity": row[3],
                "amount": float(row[4]),
                "status": row[5],
            }
        finally:
            if cur is not None:
                cur.close()
            self._db_pool.putconn(conn)
