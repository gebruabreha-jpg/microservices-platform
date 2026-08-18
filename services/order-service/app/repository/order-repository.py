from app.core.database import get_db


def create_order(order_data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (customer_id, product_id, quantity, amount, status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (order_data.customer_id, order_data.product_id, order_data.quantity, order_data.amount, order_data.status),
    )
    order_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return order_id


def get_all_orders():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, customer_id, product_id, quantity, amount, status FROM orders")
    rows = cur.fetchall()
    cur.close()
    return rows
