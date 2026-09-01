"""
Notification Service - Business Logic
"""

import json
import time
import uuid
from opentelemetry.trace import Status, StatusCode
from app.repository.notification_repository import create_notification, get_all_notifications
from app.core.database import get_rabbitmq_connection, release_db, check_dependencies, setup_dlq
from app.schema.notification_schema import NotificationCreate
from shared.tracing import get_tracer
from shared.metrics import get_metric
from shared.logging import get_logger, log_event

tracer = get_tracer("notification-service")
logger = get_logger("notification-service")

metric = get_metric()
notification_counter = metric.create_counter(
    "notification_requests_total",
    description="Total notification requests",
    unit="1",
)
notification_duration = metric.create_histogram(
    "notification_request_duration_seconds",
    description="Notification request duration in seconds",
    unit="s",
)
dlq_counter = metric.create_counter(
    "notification_dlq_total",
    description="Messages sent to DLQ",
    unit="1",
)
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

    with tracer.start_as_current_span("send_notification") as span:
        span.set_attribute("notification.type", notification_data.type)
        span.set_attribute("notification.order_id", notification_data.order_id)
        span.set_attribute("correlation_id", correlation_id)

        try:
            with tracer.start_as_current_span("db.insert_notification") as db_span:
                notification_id = create_notification(notification_data)
                db_span.set_attribute("db.rows_affected", 1)
                db_span.set_attribute("notification.id", notification_id)

            notification_counter.add(1, {"method": "POST", "endpoint": "/notifications", "status": "success"})
            log_event(logger, "info", "Notification sent", notification_id=notification_id, correlation_id=correlation_id)
            span.set_status(Status(StatusCode.OK))
            return {"id": notification_id, "status": "queued", "correlation_id": correlation_id}

        except Exception as e:
            notification_counter.add(1, {"method": "POST", "endpoint": "/notifications", "status": "error"})
            log_event(logger, "error", "Notification failed", error=str(e), correlation_id=correlation_id)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration = time.time() - start
            notification_duration.record(duration, {"endpoint": "/notifications"})


# =============================================================================
# MESSAGE HANDLERS: RabbitMQ consumers with tracing
# =============================================================================
def handle_notification(ch, method, properties, body):
    from app.schema.notification_schema import NotificationCreate

    message = json.loads(body)

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
            dlq_counter.add(1)
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
        except Exception as e:
            log_event(logger, "error", "Consumer error", error=str(e))
            time.sleep(5)


def start_dlq_consumer():
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            setup_dlq(channel)

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
        except Exception as e:
            log_event(logger, "error", "DLQ consumer error", error=str(e))
            time.sleep(5)
