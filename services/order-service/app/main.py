from fastapi import FastAPI
import redis
import psycopg2
import os
import json
import requests
from shared.models import Order

app = FastAPI()

redis_client = None
db_conn = None


def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )
    return redis_client


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


def publish_kafka_event(topic, event):
    try:
        requests.post(
            os.getenv("KAFKA_REST_URL", "http://kafka-rest:8082/topics/" + topic),
            json=event,
            timeout=5,
        )
    except Exception:
        pass


@app.get("/health")
def health():
    return {"status": "ok", "service": "order-service"}


@app.get("/metrics")
def metrics():
    r = get_redis()
    r.incr("orders_requests_total")
    return {"orders_requests_total": r.get("orders_requests_total")}


@app.get("/orders")
def list_orders():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, customer_id, product_id, quantity, amount, status FROM orders")
    rows = cur.fetchall()
    cur.close()
    return [
        {"id": r[0], "customer_id": r[1], "product_id": r[2], "quantity": r[3], "amount": float(r[4]), "status": r[5]}
        for r in rows
    ]


@app.post("/orders")
def create_order(order: Order):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (customer_id, product_id, quantity, amount, status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (order.customer_id, order.product_id, order.quantity, order.amount, "created"),
    )
    order_id = cur.fetchone()[0]
    conn.commit()
    cur.close()

    event = {"order_id": order_id, "customer_id": order.customer_id, "product_id": order.product_id, "quantity": order.quantity, "amount": order.amount, "status": "created"}
    publish_kafka_event("orders", event)

    r = get_redis()
    r.set("order:" + str(order_id), json.dumps(event))

    return {"id": order_id, "status": "created"}