"""
Payment Service - Business Logic (OOP + DI).

Swappable deps (repo/cache/publisher/health) are constructor-injected;
logging/metrics/tracing are ambient (module-level, not injected).
"""

import json
import os
import time
import uuid
from typing import Optional, List, Dict
from opentelemetry.trace import Status, StatusCode

from shared.events import EventPublisher
from shared.health import HealthChecker
from shared.repository import PaymentRepository
from shared.observability import get_service_telemetry
from app.schema.payment_schema import PaymentCreate


class PaymentService:
    """Payment business logic. Swappable dependencies (repo/publisher/health) are
    injected; logging/metrics/tracing are ambient infrastructure."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        event_publisher: EventPublisher,
        health_checker: HealthChecker,
    ):
        self._payment_repository = payment_repository
        self._event_publisher = event_publisher
        self._health_checker = health_checker
        telemetry = get_service_telemetry("payment-service", "payment", "payment")
        self._logger = telemetry.logger
        self._tracer = telemetry.tracer
        self._payment_counter = telemetry.request_counter
        self._payment_duration = telemetry.request_duration

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

            def build_event(new_payment_id):
                return "notifications", {
                    "type": "payment_received",
                    "payment_id": new_payment_id,
                    "order_id": payment.order_id,
                    "correlation_id": correlation_id,
                }

            try:
                # Idempotency check
                existing = await self._payment_repository.get_by_order_id(payment.order_id)
                if existing:
                    span.set_attribute("payment.idempotent", True)
                    return {
                        "id": existing["id"],
                        "order_id": existing["order_id"],
                        "amount": existing["amount"],
                        "status": existing["status"],
                        "correlation_id": correlation_id,
                    }

                # Database write + outbox event, atomically. The "notifications"
                # event is relayed to RabbitMQ by the outbox poller.
                with self._tracer.start_as_current_span("db.insert_payment") as db_span:
                    payment_id = await self._payment_repository.create(
                        payment, outbox_event=build_event
                    )
                    db_span.set_attribute("payment.id", payment_id)

                # Record metrics
                self._payment_counter.add(1, {"method": "POST", "endpoint": "/payments", "status": "success"})
                self._logger.info("Payment processed", payment_id=payment_id, correlation_id=correlation_id)
                span.set_status(Status(StatusCode.OK))

                return {
                    "id": payment_id,
                    "order_id": payment.order_id,
                    "amount": payment.amount,
                    "status": "processing",
                    "correlation_id": correlation_id,
                }

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


def start_kafka_consumer(stop_event=None):
    """Consume ``orders`` events and create payments. Runs in a daemon thread.

    ``stop_event`` (a threading.Event) lets the lifespan handler break the loop
    for a clean shutdown.
    """
    import asyncio
    from kafka import KafkaConsumer

    from shared.observability import get_logger, get_tracer

    logger = get_logger("payment-service.kafka_consumer")
    tracer = get_tracer("payment-service.kafka_consumer")

    # This thread has no running event loop; create one so the async service
    # methods actually execute instead of being discarded as un-awaited coroutines.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Create service instance for handling events
    from app.container import get_container
    service = get_container().get_payment_service()

    def stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    while not stopped():
        consumer = None
        try:
            consumer = KafkaConsumer(
                "orders",
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                group_id="payment-service",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            while not stopped():
                for records in consumer.poll(timeout_ms=1000).values():
                    for message in records:
                        event = message.value
                        if event.get("status") != "created":
                            continue
                        with tracer.start_as_current_span("consume_order_event") as span:
                            span.set_attribute("messaging.system", "kafka")
                            span.set_attribute("messaging.topic", "orders")
                            span.set_attribute("messaging.consumer_group", "payment-service")
                            span.set_attribute("order.id", event.get("order_id"))
                            try:
                                loop.run_until_complete(service.create_payment_from_event(event))
                            except Exception as e:
                                span.set_status(Status(StatusCode.ERROR, str(e)))
                                span.record_exception(e)
                                logger.error(
                                    "Failed to process order event",
                                    error=str(e),
                                    order_id=event.get("order_id"),
                                    correlation_id=event.get("correlation_id"),
                                )
        except Exception as e:
            if not stopped():
                logger.error("Kafka consumer error", error=str(e))
                time.sleep(5)
        finally:
            if consumer is not None:
                try:
                    consumer.close()
                except Exception:
                    pass
    logger.info("Kafka consumer stopped")
