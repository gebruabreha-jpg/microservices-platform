import json
from app.repository.order_repository import create_order, get_all_orders
from app.core.database import get_redis, publish_kafka_event
from app.schema.order_schema import OrderCreate


def health_check():
    return {"status": "ok", "service": "order-service"}


def get_metrics():
    r = get_redis()
    r.incr("orders_requests_total")
    return {"orders_requests_total": r.get("orders_requests_total")}


def list_orders():
    rows = get_all_orders()
    return [
        {
            "id": r[0],
            "customer_id": r[1],
            "product_id": r[2],
            "quantity": r[3],
            "amount": float(r[4]),
            "status": r[5],
        }
        for r in rows
    ]


def create_order(order: OrderCreate):
    order_id = create_order(order)
    event = {
        "order_id": order_id,
        "customer_id": order.customer_id,
        "product_id": order.product_id,
        "quantity": order.quantity,
        "amount": order.amount,
        "status": order.status,
    }
    publish_kafka_event("orders", event)
    get_redis().set("order:" + str(order_id), json.dumps(event))
    return {"id": order_id, "status": order.status}
