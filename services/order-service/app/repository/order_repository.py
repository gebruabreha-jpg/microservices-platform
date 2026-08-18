from app.core.database import get_db, release_db


def create_order(order_data, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (customer_id, product_id, quantity, amount, status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (order_data.customer_id, order_data.product_id, order_data.quantity, order_data.amount, order_data.status),
    )
    order_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    if own_conn:
        release_db(conn)
    return order_id


def get_all_orders(limit=20, offset=0):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, customer_id, product_id, quantity, amount, status FROM orders ORDER BY id LIMIT %s OFFSET %s",
        (limit, offset),
    )
    rows = cur.fetchall()
    cur.close()
    release_db(conn)
    return rows
