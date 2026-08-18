from app.core.database import get_db, release_db


def create_payment(payment_data, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (order_id, amount, status) VALUES (%s, %s, %s) RETURNING id",
        (payment_data.order_id, payment_data.amount, payment_data.status),
    )
    payment_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    if own_conn:
        release_db(conn)
    return payment_id


def get_all_payments(limit=20, offset=0):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, order_id, amount, status, created_at FROM payments ORDER BY id LIMIT %s OFFSET %s",
        (limit, offset),
    )
    rows = cur.fetchall()
    cur.close()
    release_db(conn)
    return rows


def get_payment_by_order_id(order_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, order_id, amount, status FROM payments WHERE order_id = %s", (order_id,))
    row = cur.fetchone()
    cur.close()
    release_db(conn)
    return row
