"""
Notification Repository Implementation.

Implements NotificationRepository interface using PostgreSQL.
"""

from typing import List, Dict
from psycopg2 import pool

from shared.interfaces import NotificationRepository


class PostgresNotificationRepository(NotificationRepository):
    """PostgreSQL implementation of NotificationRepository."""

    def __init__(self, db_pool: pool.ThreadedConnectionPool):
        self._db_pool = db_pool

    async def create(self, notification_data) -> int:
        """Create a new notification and return its ID."""
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO notifications (type, order_id, status) VALUES (%s, %s, %s) RETURNING id",
                (notification_data.type, notification_data.order_id, notification_data.status),
            )
            notification_id = cur.fetchone()[0]
            conn.commit()
            return notification_id
        finally:
            cur.close()
            self._db_pool.putconn(conn)

    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Get all notifications with pagination."""
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, type, order_id, status FROM notifications ORDER BY id LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "type": r[1],
                    "order_id": r[2],
                    "status": r[3],
                }
                for r in rows
            ]
        finally:
            cur.close()
            self._db_pool.putconn(conn)
