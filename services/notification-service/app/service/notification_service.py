import json
import time
import uuid
from prometheus_client import Counter, Histogram, CollectorRegistry
from app.repository.notification_repository import create_notification, get_all_notifications
from app.core.database import get_rabbitmq_connection, release_db, check_dependencies, setup_dlq
from app.schema.notification_schema import NotificationCreate

try:
    from prometheus_client import Counter, Histogram, CollectorRegistry
    registry = CollectorRegistry()
    REQUEST_COUNT = Counter("notification_requests_total", "Total notification requests", ["method", "endpoint", "status"], registry=registry)
    REQUEST_LATENCY = Histogram("notification_request_latency_seconds", "Notification request latency", ["endpoint"], registry=registry)
    DLQ_COUNT = Counter("notification_dlq_total", "Messages sent to DLQ", registry=registry)
except ImportError:
    REQUEST_COUNT = None
    REQUEST_LATENCY = None
    DLQ_COUNT = None


def health_check():
    deps = check_dependencies()
    status = "ok" if all(deps.values()) else "degraded"
    return {"status": status, "service": "notification-service", "dependencies": deps}


def get_metrics():
    return {"service": "notification-service"}


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
    try:
        notification_id = create_notification(notification_data)
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method="POST", endpoint="/notifications", status="success").inc()
        log_event(logger, "info", "Notification sent", notification_id=notification_id, correlation_id=correlation_id)
        return {"id": notification_id, "status": "queued", "correlation_id": correlation_id}
    except Exception as e:
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method="POST", endpoint="/notifications", status="error").inc()
        log_event(logger, "error", "Notification failed", error=str(e), correlation_id=correlation_id)
        raise
    finally:
        if REQUEST_LATENCY:
            REQUEST_LATENCY.labels(endpoint="/notifications").observe(time.time() - start)


def handle_notification(ch, method, properties, body):
    message = json.loads(body)
    from app.schema.notification_schema import NotificationCreate
    notification = NotificationCreate(
        type=message.get("type"),
        order_id=message.get("order_id"),
        status="queued",
    )
    try:
        send_notification(notification, request_id=message.get("correlation_id"))
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        if DLQ_COUNT:
            DLQ_COUNT.inc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


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

            def on_dlq_message(ch, method, properties, body):
                message = json.loads(body)
                log_event(logger, "error", "DLQ message received", message=message)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue="dlq", on_message_callback=on_dlq_message, auto_ack=False)
            channel.start_consuming()
        except Exception:
            pass
