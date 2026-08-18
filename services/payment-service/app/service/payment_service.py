import json
import os
from app.repository.payment_repository import create_payment, get_all_payments
from app.core.database import queue_rabbitmq_job
from app.schema.payment_schema import PaymentCreate


def health_check():
    return {"status": "ok", "service": "payment-service"}


def get_metrics():
    return {"service": "payment-service"}


def list_payments():
    rows = get_all_payments()
    return [
        {
            "id": r[0],
            "order_id": r[1],
            "amount": float(r[2]),
            "status": r[3],
        }
        for r in rows
    ]


def process_payment(payment: PaymentCreate):
    payment_id = create_payment(payment)
    queue_rabbitmq_job("notifications", {"type": "payment_received", "payment_id": payment_id, "order_id": payment.order_id})
    return {"id": payment_id, "status": "processing"}


def create_payment_from_event(event):
    payment = PaymentCreate(
        order_id=event.get("order_id"),
        amount=event.get("amount", 0),
        status="processing",
    )
    return process_payment(payment)


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
