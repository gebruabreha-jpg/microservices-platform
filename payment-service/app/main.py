from fastapi import FastAPI
import psycopg2
import os
import json
import requests

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


def queue_rabbitmq_job(queue, message):
    try:
        requests.post(
            os.getenv("RABBITMQ_REST_URL", "http://rabbitmq:15672/api/queues/" + queue),
            json=message,
            auth=(os.getenv("RABBITMQ_USER", "admin"), os.getenv("RABBITMQ_PASS", "secret")),
            timeout=5,
        )
    except Exception:
        pass


@app.get("/health")
def health():
    return {"status": "ok", "service": "payment-service"}


@app.get("/metrics")
def metrics():
    return {"service": "payment-service"}


@app.get("/payments")
def list_payments():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, order_id, amount, status FROM payments")
    rows = cur.fetchall()
    cur.close()
    return [{"id": r[0], "order_id": r[1], "amount": float(r[2]), "status": r[3]} for r in rows]


@app.post("/payments")
def process_payment(payment: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (order_id, amount, status) VALUES (%s, %s, %s) RETURNING id",
        (payment.get("order_id"), payment.get("amount"), "processing"),
    )
    payment_id = cur.fetchone()[0]
    conn.commit()
    cur.close()

    queue_rabbitmq_job("notifications", {"type": "payment_received", "payment_id": payment_id, "order_id": payment.get("order_id")})

    return {"id": payment_id, "status": "processing"}