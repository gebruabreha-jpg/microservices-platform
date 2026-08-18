import json
import os
import time
import uuid
import logging
from prometheus_client import Counter, Histogram, CollectorRegistry
from app.repository.payment_repository import create_payment, get_all_payments, get_payment_by_order_id
from app.core.database import queue_rabbitmq_job, release_db, check_dependencies
from app.schema.payment_schema import PaymentCreate
from shared.logger import log_event

logger = logging.getLogger("payment-service")

registry = CollectorRegistry()

registry = CollectorRegistry()

REQUEST_COUNT = Counter("payment_requests_total", "Total payment requests", ["method", "endpoint", "status"], registry=registry)
REQUEST_LATENCY = Histogram("payment_request_latency_seconds", "Payment request latency", ["endpoint"], registry=registry)


def health_check():
    deps = check_dependencies()
    status = "ok" if all(deps.values()) else "degraded"
    return {"status": status, "service": "payment-service", "dependencies": deps}


def get_metrics():
    return {"service": "payment-service"}


def list_payments(limit=20, offset=0):
    rows = get_all_payments(limit=limit, offset=offset)
    return [
        {
            "id": r[0],
            "order_id": r[1],
            "amount": float(r[2]),
            "status": r[3],
        }
        for r in rows
    ]


def process_payment(payment: PaymentCreate, request_id=None):
    start = time.time()
    correlation_id = request_id or str(uuid.uuid4())
    conn = None
    try:
        existing = get_payment_by_order_id(payment.order_id)
        if existing:
            return {"id": existing[0], "status": existing[3], "correlation_id": correlation_id, "message": "idempotent"}

        conn = get_db()
        payment_id = create_payment(payment, conn)
        queue_rabbitmq_job("notifications", {"type": "payment_received", "payment_id": payment_id, "order_id": payment.order_id, "correlation_id": correlation_id})
        REQUEST_COUNT.labels(method="POST", endpoint="/payments", status="success").inc()
        log_event(logger, "info", "Payment processed", payment_id=payment_id, correlation_id=correlation_id)
        return {"id": payment_id, "status": "processing", "correlation_id": correlation_id}
    except Exception as e:
        REQUEST_COUNT.labels(method="POST", endpoint="/payments", status="error").inc()
        log_event(logger, "error", "Payment processing failed", error=str(e), correlation_id=correlation_id)
        raise
    finally:
        REQUEST_LATENCY.labels(endpoint="/payments").observe(time.time() - start)
        if conn and db_pool:
            release_db(conn)


def create_payment_from_event(event):
    payment = PaymentCreate(
        order_id=event.get("order_id"),
        amount=event.get("amount", 0),
        status="processing",
    )
    return process_payment(payment, request_id=event.get("correlation_id"))


def start_kafka_consumer():
    from kafka import KafkaConsumer
    while True:
        try:
            consumer = KafkaConsumer(
                "orders",
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                group_id="payment-service",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            for message in consumer:
                event = message.value
                if event.get("status") == "created":
                    create_payment_from_event(event)
        except Exception:
            pass
