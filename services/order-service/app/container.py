"""
Dependency Injection Container for Order Service.

Wires dependencies only. Concrete infra adapters live in `shared/`.
"""

from shared.cache import RedisCacheClient
from shared.events import KafkaEventPublisher
from shared.factories import (
    create_circuit_breakers,
    create_db_pool,
    create_kafka_producer,
    create_redis_client,
)
from shared.health import DatabaseHealthChecker
from shared.observability import get_logger
from app.repository.order_repository import PostgresOrderRepository


class Container:
    """Dependency Injection Container - only wires dependencies."""

    def __init__(self):
        self.db_pool = create_db_pool()
        self.redis_client = create_redis_client()
        self.kafka_producer = create_kafka_producer()
        self.circuit_breakers = create_circuit_breakers()
        self._order_service = None

    def _kafka_publisher(self):
        # Pass the factory too so a producer that failed to build at startup is
        # retried lazily on the next publish.
        return KafkaEventPublisher(
            self.kafka_producer,
            self.circuit_breakers.get("kafka"),
            producer_factory=create_kafka_producer,
        )

    def get_order_service(self):
        """Return the process-wide OrderService singleton (built on first call)."""
        if self._order_service is None:
            from app.service.order_service import OrderService

            self._order_service = OrderService(
                order_repository=PostgresOrderRepository(self.db_pool),
                cache=RedisCacheClient(self.redis_client, client_factory=create_redis_client),
                event_publisher=self._kafka_publisher(),
                health_checker=DatabaseHealthChecker(self.db_pool, self.redis_client),
            )
        return self._order_service

    def get_outbox_poller(self):
        """Relays order_outbox rows to Kafka."""
        from shared.outbox import OutboxPoller

        return OutboxPoller(
            self.db_pool,
            self._kafka_publisher(),
            get_logger("order-service.outbox"),
            table="order_outbox",
        )


_container = None


def get_container() -> "Container":
    """Return the process-wide DI container (one DB pool / broker factory per service)."""
    global _container
    if _container is None:
        _container = Container()
    return _container
