from fastapi import FastAPI
import psycopg2
import os
import json
from shared.models import InventoryItem

app = FastAPI()

db_conn = None


def get_db():
    global db_conn
    if db_conn is None:
        db_conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "appdb"),
            user=os.getenv("POSTGRES_USER", "admin"),
            password=os.getenv("POSTGRES_PASSWORD", "secret"),
        )
    return db_conn


@app.get("/health")
def health():
    return {"status": "ok", "service": "inventory-service"}


@app.get("/metrics")
def metrics():
    return {"service": "inventory-service"}


@app.get("/inventory")
def list_inventory():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, product_id, quantity, reserved FROM inventory")
    rows = cur.fetchall()
    cur.close()
    return [{"id": r[0], "product_id": r[1], "quantity": r[2], "reserved": r[3]} for r in rows]


@app.post("/inventory/reserve")
def reserve_inventory(item: InventoryItem):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE inventory SET reserved = reserved + %s WHERE product_id = %s AND quantity - reserved >= %s RETURNING id",
        (item.quantity, item.product_id, item.quantity),
    )
    result = cur.fetchone()
    conn.commit()
    cur.close()
    if result is None:
        return {"error": "Insufficient inventory"}, 400
    return {"id": result[0], "status": "reserved"}