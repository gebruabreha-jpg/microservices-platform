"""
Dependency Injection Container for Payment Service.

Only wires dependencies - all implementations are in shared/implementations/.
"""

from shared.implementations import (
    create_db_pool,
    get_rabbitmq_connection_factory,
    create_circuit_breakers,
    RabbitMQEventPublisher,
    StructuredLogger,
    DatabaseHealthChecker,
    RabbitMQHealthChecker,
)
from shared.metrics import get_metric
from app.repository.payment_repository import PostgresPaymentRepository


class Container:
    """Dependency Injection Container - only wires dependencies."""

    def __init__(self):
        self.db_pool = create_db_pool()
        self.rabbitmq_factory = get_rabbitmq_connection_factory()
        self.circuit_breakers = create_circuit_breakers()

    def _rabbitmq_publisher(self):
        return RabbitMQEventPublisher(self.rabbitmq_factory, self.circuit_breakers.get("rabbitmq"))

    def get_payment_service(self):
        """Create PaymentService with all dependencies injected."""
        from app.service.payment_service import PaymentService

        return PaymentService(
            payment_repository=PostgresPaymentRepository(self.db_pool),
            event_publisher=self._rabbitmq_publisher(),
            metrics=get_metric(),
            logger=StructuredLogger("payment-service"),
            health_checker=DatabaseHealthChecker(self.db_pool),
        )

    def get_outbox_poller(self):
        """Create the outbox poller that relays payment_outbox rows to RabbitMQ."""
        from shared.outbox import OutboxPoller

        return OutboxPoller(
            self.db_pool,
            self._rabbitmq_publisher(),
            StructuredLogger("payment-service.outbox"),
            table="payment_outbox",
        )


_container = None


def get_container() -> "Container":
    """Return the process-wide DI container (one DB pool / broker factory per service)."""
    global _container
    if _container is None:
        _container = Container()
    return _container
