"""
Dependency Injection Container for Payment Service.

Wires dependencies only. Concrete infra adapters live in `shared/`.
"""

from shared.events import RabbitMQEventPublisher
from shared.factories import (
    create_circuit_breakers,
    create_db_pool,
    get_rabbitmq_connection_factory,
)
from shared.health import DatabaseHealthChecker
from shared.observability import get_logger
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
        from app.service.payment_service import PaymentService

        return PaymentService(
            payment_repository=PostgresPaymentRepository(self.db_pool),
            event_publisher=self._rabbitmq_publisher(),
            health_checker=DatabaseHealthChecker(self.db_pool),
        )

    def get_outbox_poller(self):
        """Relays payment_outbox rows to the RabbitMQ 'notifications' queue."""
        from shared.outbox import OutboxPoller

        return OutboxPoller(
            self.db_pool,
            self._rabbitmq_publisher(),
            get_logger("payment-service.outbox"),
            table="payment_outbox",
        )


_container = None


def get_container() -> "Container":
    """Return the process-wide DI container (one DB pool / broker factory per service)."""
    global _container
    if _container is None:
        _container = Container()
    return _container
