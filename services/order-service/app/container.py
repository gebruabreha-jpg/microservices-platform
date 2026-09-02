"""
Dependency Injection Container for Order Service.

Only wires dependencies - all implementations are in shared/implementations/.
"""

from shared.implementations import (
    create_db_pool,
    create_redis_client,
    create_kafka_producer,
    create_circuit_breakers,
    RedisCacheClient,
    KafkaEventPublisher,
    StructuredLogger,
    DatabaseHealthChecker,
)
from shared.metrics import get_metric
from app.repository.order_repository import PostgresOrderRepository


class Container:
    """Dependency Injection Container - only wires dependencies."""

    def __init__(self):
        self.db_pool = create_db_pool()
        self.redis_client = create_redis_client()
        self.kafka_producer = create_kafka_producer()
        self.circuit_breakers = create_circuit_breakers()

    def _kafka_publisher(self):
        # Pass the factory too so a producer that failed to build at startup is
        # retried lazily on the next publish.
        return KafkaEventPublisher(
            self.kafka_producer,
            self.circuit_breakers.get("kafka"),
            producer_factory=create_kafka_producer,
        )

    def get_order_service(self):
        """Create OrderService with all dependencies injected."""
        from app.service.order_service import OrderService

        return OrderService(
            order_repository=PostgresOrderRepository(self.db_pool),
            cache=RedisCacheClient(self.redis_client),
            event_publisher=self._kafka_publisher(),
            metrics=get_metric(),
            logger=StructuredLogger("order-service"),
            health_checker=DatabaseHealthChecker(self.db_pool, self.redis_client),
        )

    def get_outbox_poller(self):
        """Create the outbox poller that relays order_outbox rows to Kafka."""
        from shared.outbox import OutboxPoller

        return OutboxPoller(
            self.db_pool,
            self._kafka_publisher(),
            StructuredLogger("order-service.outbox"),
            table="order_outbox",
        )


_container = None


def get_container() -> "Container":
    """Return the process-wide DI container (one DB pool / broker factory per service)."""
    global _container
    if _container is None:
        _container = Container()
    return _container
