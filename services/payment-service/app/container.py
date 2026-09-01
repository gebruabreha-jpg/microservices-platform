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

    def get_payment_service(self):
        """Create PaymentService with all dependencies injected."""
        from app.service.payment_service import PaymentService

        return PaymentService(
            payment_repository=PostgresPaymentRepository(self.db_pool),
            event_publisher=RabbitMQEventPublisher(
                self.rabbitmq_factory,
                self.circuit_breakers.get("rabbitmq"),
            ),
            metrics=get_metric(),
            logger=StructuredLogger("payment-service"),
            health_checker=DatabaseHealthChecker(self.db_pool),
        )
