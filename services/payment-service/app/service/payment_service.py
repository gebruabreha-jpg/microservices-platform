"""
Payment Service - Business Logic (OOP + DI).

Follows:
- Single Responsibility Principle: Each method does one thing
- Dependency Inversion: Depends on interfaces, not implementations
- Open/Closed: Can extend without modifying
"""

import json
import os
import time
import uuid
from typing import Optional, List, Dict
from opentelemetry.trace import Status, StatusCode

from shared.interfaces import (
    PaymentRepository,
    EventPublisher,
    MetricsClient,
    Logger,
    HealthChecker,
)
from shared.tracing import get_tracer
from app.schema.payment_schema import PaymentCreate


class PaymentService:
    """
    Payment service with dependency injection.

    All dependencies are injected through the constructor,
    following the Dependency Inversion Principle.
    """

    def __init__(
        self,
        payment_repository: PaymentRepository,
        event_publisher: EventPublisher,
        metrics: MetricsClient,
        logger: Logger,
        health_checker: HealthChecker,
    ):
        self._payment_repository = payment_repository
        self._event_publisher = event_publisher
        self._metrics = metrics
        self._logger = logger
        self._health_checker = health_checker
        self._tracer = get_tracer("payment-service")

        # Initialize metrics
        self._payment_counter = metrics.create_counter(
            "payment_requests_total",
            description="Total payment requests",
            unit="1",
        )
        self._payment_duration = metrics.create_histogram(
            "payment_request_duration_seconds",
            description="Payment request duration in seconds",
            unit="s",
        )

    async def health_check(self) -> Dict:
        """Check service health."""
        deps = await self._health_checker.check()
        status = "ok" if all(deps.values()) else "degraded"
        return {"status": status, "service": "payment-service", "dependencies": deps}

    async def list_payments(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """List payments with pagination."""
        return await self._payment_repository.get_all(limit=limit, offset=offset)

    async def process_payment(self, payment: PaymentCreate, request_id: Optional[str] = None) -> Dict:
        """Process a new payment."""
        start = time.time()
        correlation_id = request_id or str(uuid.uuid4())

        with self._tracer.start_as_current_span("process_payment") as span:
            span.set_attribute("payment.order_id", payment.order_id)
            span.set_attribute("payment.amount", payment.amount)
            span.set_attribute("correlation_id", correlation_id)

            try:
                # Idempotency check
                existing = await self._payment_repository.get_by_order_id(payment.order_id)
                if existing:
                    span.set_attribute("payment.idempotent", True)
                    return {"id": existing["id"], "status": existing["status"], "correlation_id": correlation_id, "message": "idempotent"}

                # Database operation
                with self._tracer.start_as_current_span("db.insert_payment") as db_span:
                    payment_id = await self._payment_repository.create(payment)
                    db_span.set_attribute("payment.id", payment_id)

                # Publish event
                with self._tracer.start_as_current_span("rabbitmq.publish_notification") as mq_span:
                    await self._event_publisher.publish("notifications", {
                        "type": "payment_received",
                        "payment_id": payment_id,
                        "order_id": payment.order_id,
                        "correlation_id": correlation_id,
                    })
                    mq_span.set_attribute("messaging.system", "rabbitmq")
                    mq_span.set_attribute("messaging.destination", "notifications")
                    mq_span.set_attribute("payment.id", payment_id)

                # Record metrics
                self._payment_counter.add(1, {"method": "POST", "endpoint": "/payments", "status": "success"})
                self._logger.info("Payment processed", payment_id=payment_id, correlation_id=correlation_id)
                span.set_status(Status(StatusCode.OK))

                return {"id": payment_id, "status": "processing", "correlation_id": correlation_id}

            except Exception as e:
                self._payment_counter.add(1, {"method": "POST", "endpoint": "/payments", "status": "error"})
                self._logger.error("Payment processing failed", error=str(e), correlation_id=correlation_id)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start
                self._payment_duration.record(duration, {"endpoint": "/payments"})

    async def create_payment_from_event(self, event: dict) -> Dict:
        """Create payment from Kafka event."""
        payment = PaymentCreate(
            order_id=event.get("order_id"),
            amount=event.get("amount", 0),
            status="processing",
        )
        return await self.process_payment(payment, request_id=event.get("correlation_id"))


def start_kafka_consumer():
    """Start Kafka consumer in a background thread."""
    from kafka import KafkaConsumer
    from opentelemetry import trace
    from shared.logging import get_logger, log_event

    logger = get_logger("payment-service.kafka_consumer")
    tracer = trace.get_tracer("payment-service.kafka_consumer")

    # Create service instance for handling events
    from app.container import Container
    container = Container()
    service = container.get_payment_service()

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
                    with tracer.start_as_current_span("consume_order_event") as span:
                        span.set_attribute("messaging.system", "kafka")
                        span.set_attribute("messaging.topic", "orders")
                        span.set_attribute("messaging.consumer_group", "payment-service")
                        span.set_attribute("order.id", event.get("order_id"))
                        service.create_payment_from_event(event)
        except Exception as e:
            log_event(logger, "error", "Kafka consumer error", error=str(e))
            time.sleep(5)
