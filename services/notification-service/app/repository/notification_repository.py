from app.core.database import get_db, release_db


def create_notification(notification_data, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_db()
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
        if own_conn:
            release_db(conn)


def get_all_notifications(limit=20, offset=0):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, type, order_id, status, created_at FROM notifications ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        rows = cur.fetchall()
        return rows
    finally:
        cur.close()
        release_db(conn)
