"""
Notification Service - Business Logic

TRACING:
  Custom spans wrap notification handling and RabbitMQ consumption:
  - RabbitMQ message handling spans
  - Database insert spans
  - DLQ processing spans

METRICS:
  - notification_requests_total counter (OTLP)
  - notification_request_duration_seconds histogram (OTLP)
  - notification_dlq_total counter (OTLP)

LOGGING:
  Structured JSON logs with trace_id/span_id for correlation.
"""

import json
import time
import uuid
import logging
from opentelemetry.trace import Status, StatusCode
from prometheus_client import Counter, Histogram
from app.repository.notification_repository import create_notification, get_all_notifications
from app.core.database import get_rabbitmq_connection, release_db, check_dependencies, setup_dlq
from app.schema.notification_schema import NotificationCreate
from shared.tracing import get_tracer
from shared.metrics import get_meter
from shared.logging import log_event

# =============================================================================
# LOGGING: Structured JSON to stdout -> Promtail -> Loki
# =============================================================================
logger = logging.getLogger("notification-service")

# =============================================================================
# TRACING: Get tracer for custom spans
# =============================================================================
tracer = get_tracer("notification-service")

# =============================================================================
# METRICS: OTLP metrics (primary) + Prometheus client (fallback)
# =============================================================================
meter = get_meter()

try:
    otlp_request_count = meter.create_counter(
        "notification_requests_total",
        description="Total notification requests",
        unit="1"
    )
    otlp_request_duration = meter.create_histogram(
        "notification_request_duration_seconds",
        description="Notification request duration in seconds",
        unit="s"
    )
    otlp_dlq_count = meter.create_counter(
        "notification_dlq_total",
        description="Messages sent to DLQ",
        unit="1"
    )

    REQUEST_COUNT = Counter("notification_requests_total", "Total notification requests", ["method", "endpoint", "status"])
    REQUEST_LATENCY = Histogram("notification_request_latency_seconds", "Notification request latency", ["endpoint"])
    DLQ_COUNT = Counter("notification_dlq_total", "Messages sent to DLQ")
except ImportError:
    otlp_request_count = None
    otlp_request_duration = None
    otlp_dlq_count = None
    REQUEST_COUNT = None
    REQUEST_LATENCY = None
    DLQ_COUNT = None


# =============================================================================
# HEALTH CHECK
# =============================================================================
def health_check():
    deps = check_dependencies()
    status = "ok" if all(deps.values()) else "degraded"
    return {"status": status, "service": "notification-service", "dependencies": deps}


# =============================================================================
# LEGACY METRICS (kept for /metrics endpoint)
# =============================================================================
def get_metrics():
    return {"service": "notification-service"}


# =============================================================================
# NOTIFICATION OPERATIONS
# =============================================================================
def list_notifications(limit=20, offset=0):
    rows = get_all_notifications(limit=limit, offset=offset)
    return [
        {
            "id": r[0],
            "type": r[1],
            "order_id": r[2],
            "status": r[3],
        }
        for r in rows
    ]


def send_notification(notification_data, request_id=None):
    start = time.time()
    correlation_id = request_id or str(uuid.uuid4())

    # =========================================================================
    # TRACING: Custom span for notification sending
    # =========================================================================
    with tracer.start_as_current_span("send_notification") as span:
        span.set_attribute("notification.type", notification_data.get("type", "unknown"))
        span.set_attribute("notification.order_id", notification_data.get("order_id"))
        span.set_attribute("correlation_id", correlation_id)

        try:
            # =========================================================================
            # TRACING: Database insert span
            # =========================================================================
            with tracer.start_as_current_span("db.insert_notification") as db_span:
                notification_id = create_notification(notification_data)
                db_span.set_attribute("db.rows_affected", 1)
                db_span.set_attribute("notification.id", notification_id)

            # =========================================================================
            # METRICS: Record success
            # =========================================================================
            if otlp_request_count:
                otlp_request_count.add(1, {"method": "POST", "endpoint": "/notifications", "status": "success"})
            if REQUEST_COUNT:
                REQUEST_COUNT.labels(method="POST", endpoint="/notifications", status="success").inc()

            log_event(logger, "info", "Notification sent", notification_id=notification_id, correlation_id=correlation_id)
            span.set_status(Status(StatusCode.OK))
            return {"id": notification_id, "status": "queued", "correlation_id": correlation_id}

        except Exception as e:
            if otlp_request_count:
                otlp_request_count.add(1, {"method": "POST", "endpoint": "/notifications", "status": "error"})
            if REQUEST_COUNT:
                REQUEST_COUNT.labels(method="POST", endpoint="/notifications", status="error").inc()

            log_event(logger, "error", "Notification failed", error=str(e), correlation_id=correlation_id)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration = time.time() - start
            if otlp_request_duration:
                otlp_request_duration.record(duration, {"endpoint": "/notifications"})
            if REQUEST_LATENCY:
                REQUEST_LATENCY.labels(endpoint="/notifications").observe(duration)


# =============================================================================
# MESSAGE HANDLERS: RabbitMQ consumers with tracing
# =============================================================================
def handle_notification(ch, method, properties, body):
    from app.schema.notification_schema import NotificationCreate
    from opentelemetry import trace

    message = json.loads(body)

    # =========================================================================
    # TRACING: RabbitMQ message handling span
    # =========================================================================
    with tracer.start_as_current_span("handle_notification") as span:
        span.set_attribute("messaging.system", "rabbitmq")
        span.set_attribute("messaging.queue", "notifications")
        span.set_attribute("messaging.message_id", message.get("correlation_id", "unknown"))

        notification = NotificationCreate(
            type=message.get("type"),
            order_id=message.get("order_id"),
            status="queued",
        )
        try:
            send_notification(notification, request_id=message.get("correlation_id"))
            ch.basic_ack(delivery_tag=method.delivery_tag)
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            if otlp_dlq_count:
                otlp_dlq_count.add(1)
            if DLQ_COUNT:
                DLQ_COUNT.inc()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)


def start_consumer():
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            setup_dlq(channel)
            channel.queue_declare(queue="notifications", durable=True, arguments={"x-dead-letter-exchange": "dlx"})
            channel.basic_consume(queue="notifications", on_message_callback=handle_notification, auto_ack=False)
            channel.start_consuming()
        except Exception:
            pass


def start_dlq_consumer():
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            setup_dlq(channel)

            # =========================================================================
            # TRACING: DLQ consumer span
            # =========================================================================
            def on_dlq_message(ch, method, properties, body):
                message = json.loads(body)
                with tracer.start_as_current_span("handle_dlq_message") as span:
                    span.set_attribute("messaging.system", "rabbitmq")
                    span.set_attribute("messaging.queue", "dlq")
                    span.set_attribute("messaging.message_id", message.get("correlation_id", "unknown"))
                    log_event(logger, "error", "DLQ message received", message=message)
                    span.set_status(Status(StatusCode.OK))
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue="dlq", on_message_callback=on_dlq_message, auto_ack=False)
            channel.start_consuming()
        except Exception:
            pass
