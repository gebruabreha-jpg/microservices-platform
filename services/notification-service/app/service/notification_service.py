"""
Notification Service - Business Logic (OOP + DI)

Follows:
- Single Responsibility Principle: Each method does one thing
- Dependency Inversion: Depends on interfaces, not implementations
- Open/Closed: Can extend without modifying
"""

import json
import time
import uuid
from typing import Optional, List, Dict
from opentelemetry.trace import Status, StatusCode

from shared.interfaces import (
    NotificationRepository,
    EventPublisher,
    MetricsClient,
    Logger,
    HealthChecker,
)
from shared.tracing import get_tracer


class NotificationService:
    """
    Notification service with dependency injection.

    All dependencies are injected through the constructor,
    following the Dependency Inversion Principle.
    """

    def __init__(
        self,
        notification_repository: NotificationRepository,
        event_publisher: EventPublisher,
        metrics: MetricsClient,
        logger: Logger,
        health_checker: HealthChecker,
    ):
        self._notification_repository = notification_repository
        self._event_publisher = event_publisher
        self._metrics = metrics
        self._logger = logger
        self._health_checker = health_checker
        self._tracer = get_tracer("notification-service")

        # Initialize metrics
        self._notification_counter = metrics.create_counter(
            "notification_requests_total",
            description="Total notification requests",
            unit="1",
        )
        self._notification_duration = metrics.create_histogram(
            "notification_request_duration_seconds",
            description="Notification request duration in seconds",
            unit="s",
        )
        self._dlq_counter = metrics.create_counter(
            "notification_dlq_total",
            description="Messages sent to DLQ",
            unit="1",
        )

    async def health_check(self) -> Dict:
        """Check service health."""
        deps = await self._health_checker.check()
        status = "ok" if all(deps.values()) else "degraded"
        return {"status": status, "service": "notification-service", "dependencies": deps}

    async def send_notification(self, notification_data, request_id: Optional[str] = None) -> Dict:
        """Send a new notification."""
        start = time.time()
        correlation_id = request_id or str(uuid.uuid4())

        with self._tracer.start_as_current_span("send_notification") as span:
            span.set_attribute("notification.type", notification_data.type)
            span.set_attribute("notification.order_id", notification_data.order_id)
            span.set_attribute("correlation_id", correlation_id)

            try:
                with self._tracer.start_as_current_span("db.insert_notification") as db_span:
                    notification_id = await self._notification_repository.create(notification_data)
                    db_span.set_attribute("notification.id", notification_id)

                self._notification_counter.add(1, {"method": "POST", "endpoint": "/notifications", "status": "success"})
                self._logger.info("Notification sent", notification_id=notification_id, correlation_id=correlation_id)
                span.set_status(Status(StatusCode.OK))

                return {"id": notification_id, "status": "queued", "correlation_id": correlation_id}

            except Exception as e:
                self._notification_counter.add(1, {"method": "POST", "endpoint": "/notifications", "status": "error"})
                self._logger.error("Notification failed", error=str(e), correlation_id=correlation_id)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start
                self._notification_duration.record(duration, {"endpoint": "/notifications"})

    async def list_notifications(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """List notifications with pagination."""
        return await self._notification_repository.get_all(limit=limit, offset=offset)

    async def handle_notification(self, ch, method, properties, body) -> None:
        """Handle incoming notification from RabbitMQ."""
        from app.schema.notification_schema import NotificationCreate

        message = json.loads(body)

        with self._tracer.start_as_current_span("handle_notification") as span:
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("messaging.queue", "notifications")
            span.set_attribute("messaging.message_id", message.get("correlation_id", "unknown"))

            notification = NotificationCreate(
                type=message.get("type"),
                order_id=message.get("order_id"),
                status="queued",
            )
            try:
                await self.send_notification(notification, request_id=message.get("correlation_id"))
                ch.basic_ack(delivery_tag=method.delivery_tag)
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                self._dlq_counter.add(1)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)

    async def start_consumer(self) -> None:
        """Start RabbitMQ consumer."""
        from app.core.database import get_rabbitmq_connection, setup_dlq

        while True:
            try:
                connection = get_rabbitmq_connection()
                channel = connection.channel()
                setup_dlq(channel)
                channel.queue_declare(queue="notifications", durable=True, arguments={"x-dead-letter-exchange": "dlx"})
                channel.basic_consume(queue="notifications", on_message_callback=self.handle_notification, auto_ack=False)
                channel.start_consuming()
            except Exception as e:
                self._logger.error("Consumer error", error=str(e))
                time.sleep(5)

    async def start_dlq_consumer(self) -> None:
        """Start DLQ consumer."""
        from app.core.database import get_rabbitmq_connection, setup_dlq

        while True:
            try:
                connection = get_rabbitmq_connection()
                channel = connection.channel()
                setup_dlq(channel)

                def on_dlq_message(ch, method, properties, body):
                    message = json.loads(body)
                    with self._tracer.start_as_current_span("handle_dlq_message") as span:
                        span.set_attribute("messaging.system", "rabbitmq")
                        span.set_attribute("messaging.queue", "dlq")
                        self._logger.error("DLQ message received", message=message)
                        span.set_status(Status(StatusCode.OK))
                    ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_consume(queue="dlq", on_message_callback=on_dlq_message, auto_ack=False)
                channel.start_consuming()
            except Exception as e:
                self._logger.error("DLQ consumer error", error=str(e))
                time.sleep(5)
