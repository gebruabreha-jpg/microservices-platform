"""
Payment Service - Business Logic

TRACING:
  Custom spans wrap payment processing and Kafka consumption:
  - Kafka message consumption spans
  - Database insert spans
  - RabbitMQ publish spans

METRICS:
  - payment_requests_total counter (OTLP)
  - payment_request_duration_seconds histogram (OTLP)

LOGGING:
  Structured JSON logs with trace_id/span_id for correlation.
"""

import json
import os
import time
import uuid
import logging
from opentelemetry.trace import Status, StatusCode
from prometheus_client import Counter, Histogram
from app.repository.payment_repository import create_payment, get_all_payments, get_payment_by_order_id
from app.core.database import queue_rabbitmq_job, release_db, check_dependencies
from app.schema.payment_schema import PaymentCreate
from shared.telemetry import get_tracer, get_meter, log_event

# =============================================================================
# LOGGING: Structured JSON to stdout -> Promtail -> Loki
# =============================================================================
logger = logging.getLogger("payment-service")

# =============================================================================
# TRACING: Get tracer for custom spans
# =============================================================================
tracer = get_tracer("payment-service")

# =============================================================================
# METRICS: OTLP metrics (primary) + Prometheus client (fallback)
# =============================================================================
meter = get_meter()

try:
    otlp_request_count = meter.create_counter(
        "payment_requests_total",
        description="Total payment requests",
        unit="1"
    )
    otlp_request_duration = meter.create_histogram(
        "payment_request_duration_seconds",
        description="Payment request duration in seconds",
        unit="s"
    )

    REQUEST_COUNT = Counter("payment_requests_total", "Total payment requests", ["method", "endpoint", "status"])
    REQUEST_LATENCY = Histogram("payment_request_latency_seconds", "Payment request latency", ["endpoint"])
except ImportError:
    otlp_request_count = None
    otlp_request_duration = None
    REQUEST_COUNT = None
    REQUEST_LATENCY = None


# =============================================================================
# HEALTH CHECK
# =============================================================================
def health_check():
    deps = check_dependencies()
    status = "ok" if all(deps.values()) else "degraded"
    return {"status": status, "service": "payment-service", "dependencies": deps}


# =============================================================================
# LEGACY METRICS (kept for /metrics endpoint)
# =============================================================================
def get_metrics():
    return {"service": "payment-service"}


# =============================================================================
# PAYMENT OPERATIONS
# =============================================================================
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

    # =========================================================================
    # TRACING: Custom span for payment processing
    # =========================================================================
    with tracer.start_as_current_span("process_payment") as span:
        span.set_attribute("payment.order_id", payment.order_id)
        span.set_attribute("payment.amount", payment.amount)
        span.set_attribute("correlation_id", correlation_id)

        try:
            # Idempotency check
            existing = get_payment_by_order_id(payment.order_id)
            if existing:
                span.set_attribute("payment.idempotent", True)
                return {"id": existing[0], "status": existing[3], "correlation_id": correlation_id, "message": "idempotent"}

            # =========================================================================
            # TRACING: Database insert span
            # =========================================================================
            with tracer.start_as_current_span("db.insert_payment") as db_span:
                conn = get_db()
                payment_id = create_payment(payment, conn)
                db_span.set_attribute("db.rows_affected", 1)
                db_span.set_attribute("payment.id", payment_id)

            # =========================================================================
            # TRACING: RabbitMQ publish span
            # =========================================================================
            with tracer.start_as_current_span("rabbitmq.publish_notification") as mq_span:
                queue_rabbitmq_job("notifications", {
                    "type": "payment_received",
                    "payment_id": payment_id,
                    "order_id": payment.order_id,
                    "correlation_id": correlation_id,
                })
                mq_span.set_attribute("messaging.system", "rabbitmq")
                mq_span.set_attribute("messaging.destination", "notifications")
                mq_span.set_attribute("payment.id", payment_id)

            # =========================================================================
            # METRICS: Record success
            # =========================================================================
            if otlp_request_count:
                otlp_request_count.add(1, {"method": "POST", "endpoint": "/payments", "status": "success"})
            if REQUEST_COUNT:
                REQUEST_COUNT.labels(method="POST", endpoint="/payments", status="success").inc()

            log_event(logger, "info", "Payment processed", payment_id=payment_id, correlation_id=correlation_id)
            span.set_status(Status(StatusCode.OK))
            return {"id": payment_id, "status": "processing", "correlation_id": correlation_id}

        except Exception as e:
            if otlp_request_count:
                otlp_request_count.add(1, {"method": "POST", "endpoint": "/payments", "status": "error"})
            if REQUEST_COUNT:
                REQUEST_COUNT.labels(method="POST", endpoint="/payments", status="error").inc()

            log_event(logger, "error", "Payment processing failed", error=str(e), correlation_id=correlation_id)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration = time.time() - start
            if otlp_request_duration:
                otlp_request_duration.record(duration, {"endpoint": "/payments"})
            if REQUEST_LATENCY:
                REQUEST_LATENCY.labels(endpoint="/payments").observe(duration)
            if conn:
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
    from opentelemetry import trace
    tracer = trace.get_tracer("payment-service.kafka_consumer")

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
                    # =========================================================================
                    # TRACING: Kafka consumption span
                    # =========================================================================
                    with tracer.start_as_current_span("consume_order_event") as span:
                        span.set_attribute("messaging.system", "kafka")
                        span.set_attribute("messaging.topic", "orders")
                        span.set_attribute("messaging.consumer_group", "payment-service")
                        span.set_attribute("order.id", event.get("order_id"))
                        create_payment_from_event(event)
        except Exception:
            pass
