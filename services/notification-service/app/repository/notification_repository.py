from app.core.database import get_db


def create_notification(notification_data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO notifications (type, order_id, status) VALUES (%s, %s, %s) RETURNING id",
        (notification_data.type, notification_data.order_id, notification_data.status),
    )
    notification_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return notification_id


def get_all_notifications():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, type, order_id, status, created_at FROM notifications")
    rows = cur.fetchall()
    cur.close()
    return rows
