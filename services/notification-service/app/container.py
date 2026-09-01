"""
Dependency Injection Container for Notification Service.

Only wires dependencies - all implementations are in shared/implementations/.
"""

from shared.implementations import (
    create_db_pool,
    get_rabbitmq_connection_factory,
    create_circuit_breakers,
    RabbitMQEventPublisher,
    StructuredLogger,
    RabbitMQHealthChecker,
)
from shared.metrics import get_metric
from app.repository.notification_repository import PostgresNotificationRepository


class Container:
    """Dependency Injection Container - only wires dependencies."""

    def __init__(self):
        self.db_pool = create_db_pool()
        self.rabbitmq_connection_factory = get_rabbitmq_connection_factory()
        self.circuit_breakers = create_circuit_breakers()

    def get_notification_service(self):
        """Create NotificationService with all dependencies injected."""
        from app.service.notification_service import NotificationService

        return NotificationService(
            notification_repository=PostgresNotificationRepository(self.db_pool),
            event_publisher=RabbitMQEventPublisher(
                self.rabbitmq_connection_factory,
                self.circuit_breakers.get("rabbitmq"),
            ),
            metrics=get_metric(),
            logger=StructuredLogger("notification-service"),
            health_checker=RabbitMQHealthChecker(self.rabbitmq_connection_factory),
        )
