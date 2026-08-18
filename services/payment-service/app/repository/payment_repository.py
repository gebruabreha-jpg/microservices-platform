from app.core.database import get_db


def create_payment(payment_data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (order_id, amount, status) VALUES (%s, %s, %s) RETURNING id",
        (payment_data.order_id, payment_data.amount, payment_data.status),
    )
    payment_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return payment_id


def get_all_payments():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, order_id, amount, status, created_at FROM payments")
    rows = cur.fetchall()
    cur.close()
    return rows
