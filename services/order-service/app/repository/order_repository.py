"""
Order Repository Implementation.

Implements OrderRepository interface using PostgreSQL.
"""

from typing import List, Dict
from psycopg2 import pool

from shared.interfaces import OrderRepository


class PostgresOrderRepository(OrderRepository):
    """PostgreSQL implementation of OrderRepository."""

    def __init__(self, db_pool: pool.ThreadedConnectionPool):
        self._db_pool = db_pool

    async def create(self, order_data) -> int:
        """Create a new order and return its ID."""
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO orders (customer_id, product_id, quantity, amount, status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (order_data.customer_id, order_data.product_id, order_data.quantity, order_data.amount, order_data.status),
            )
            order_id = cur.fetchone()[0]
            conn.commit()
            return order_id
        finally:
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
