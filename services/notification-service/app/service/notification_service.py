"""
Notification Service - Business Logic (OOP + DI)

Swappable deps (repo/cache/publisher/health) are constructor-injected;
logging/metrics/tracing are ambient (module-level, not injected).
"""

import asyncio
import json
import threading
import time
import uuid
from typing import Optional, List, Dict
from opentelemetry.trace import Status, StatusCode

from shared.events import EventPublisher
from shared.health import HealthChecker
from shared.repository import NotificationRepository
from shared.observability import get_logger, get_metric, get_tracer


class NotificationService:
    """Notification business logic + RabbitMQ consumers. Swappable dependencies
    (repo/publisher/health) are injected; logging/metrics/tracing are ambient."""

    def __init__(
        self,
        notification_repository: NotificationRepository,
        event_publisher: EventPublisher,
        health_checker: HealthChecker,
    ):
        self._notification_repository = notification_repository
        self._event_publisher = event_publisher
        self._health_checker = health_checker
        self._logger = get_logger("notification-service")
        self._tracer = get_tracer("notification-service")
        # Dedicated event loop for the blocking RabbitMQ consumer thread.
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Set on shutdown to break the consumer loops cleanly.
        self._stop = threading.Event()

        metrics = get_metric()
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

                return {
                    "id": notification_id,
                    "type": notification_data.type,
                    "order_id": notification_data.order_id,
                    "status": "queued",
                    "correlation_id": correlation_id,
                }

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

    def _handle_message_body(self, body) -> None:
        """Parse and persist one notification message (synchronous).

        Runs the async ``send_notification`` path on the consumer thread's
        private event loop. Raises on any failure so the caller can dead-letter.
        """
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
            self._loop.run_until_complete(
                self.send_notification(notification, request_id=message.get("correlation_id"))
            )
            span.set_status(Status(StatusCode.OK))

    def stop(self) -> None:
        """Signal the consumer loops to exit (called on application shutdown)."""
        self._stop.set()

    def _consume_forever(self, queue: str, on_message, *, span_label: str) -> None:
        """Shared reconnect/poll loop for a blocking pika consumer.

        Uses ``process_data_events`` rather than ``start_consuming`` so the
        ``_stop`` event is checked roughly once a second and shutdown is clean.
        """
        from app.core.database import get_rabbitmq_connection, setup_dlq

        while not self._stop.is_set():
            connection = None
            try:
                connection = get_rabbitmq_connection()
                channel = connection.channel()
                setup_dlq(channel)
                if queue == "notifications":
                    # Matches rabbitmq/definitions.json exactly (incl. the DLX
                    # args) so redeclaration never trips PRECONDITION_FAILED.
                    channel.queue_declare(
                        queue="notifications",
                        durable=True,
                        arguments={
                            "x-dead-letter-exchange": "dlx",
                            "x-dead-letter-routing-key": "dlq",
                        },
                    )
                channel.basic_qos(prefetch_count=10)
                channel.basic_consume(queue=queue, on_message_callback=on_message, auto_ack=False)
                self._logger.info(f"{span_label} started", queue=queue)
                while not self._stop.is_set():
                    connection.process_data_events(time_limit=1)
            except Exception as e:
                if not self._stop.is_set():
                    self._logger.error(f"{span_label} error, reconnecting in 5s", error=str(e))
                    self._stop.wait(5)
            finally:
                if connection is not None and connection.is_open:
                    try:
                        connection.close()
                    except Exception:
                        pass
        self._logger.info(f"{span_label} stopped", queue=queue)

    def start_consumer(self) -> None:
        """Consume notification messages from RabbitMQ (blocking; daemon thread).

        A message that fails processing is nacked without requeue, so the broker
        dead-letters it to the ``dlx`` exchange / ``dlq`` queue.
        """
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        def on_message(ch, method, properties, body):
            try:
                self._handle_message_body(body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                self._dlq_counter.add(1)
                self._logger.error("Notification handling failed, dead-lettering", error=str(e))
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        self._consume_forever("notifications", on_message, span_label="Notification consumer")

    def start_dlq_consumer(self) -> None:
        """Consume dead-lettered messages for logging and alerting (blocking; daemon thread)."""

        def on_dlq_message(ch, method, properties, body):
            try:
                message = json.loads(body)
            except ValueError:
                message = {"raw": body.decode("utf-8", "replace")}
            with self._tracer.start_as_current_span("handle_dlq_message") as span:
                span.set_attribute("messaging.system", "rabbitmq")
                span.set_attribute("messaging.queue", "dlq")
                self._logger.error("DLQ message received", message=message)
                span.set_status(Status(StatusCode.OK))
            ch.basic_ack(delivery_tag=method.delivery_tag)

        self._consume_forever("dlq", on_dlq_message, span_label="DLQ consumer")
