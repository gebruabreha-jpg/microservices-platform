"""
Dependency Injection Container for Notification Service.

Wires dependencies only. Concrete infra adapters live in `shared/`.
"""

from shared.events import RabbitMQEventPublisher
from shared.factories import create_circuit_breakers, create_db_pool, get_rabbitmq_connection_factory
from shared.health import RabbitMQHealthChecker
from app.repository.notification_repository import PostgresNotificationRepository


class Container:
    """Dependency Injection Container - only wires dependencies."""

    def __init__(self):
        self.db_pool = create_db_pool()
        self.rabbitmq_connection_factory = get_rabbitmq_connection_factory()
        self.circuit_breakers = create_circuit_breakers()
        self._notification_service = None

    def get_notification_service(self):
        """Return the process-wide NotificationService singleton (built on first call)."""
        if self._notification_service is None:
            from app.service.notification_service import NotificationService

            self._notification_service = NotificationService(
                notification_repository=PostgresNotificationRepository(self.db_pool),
                event_publisher=RabbitMQEventPublisher(
                    self.rabbitmq_connection_factory,
                    self.circuit_breakers.get("rabbitmq"),
                ),
                health_checker=RabbitMQHealthChecker(self.rabbitmq_connection_factory),
            )
        return self._notification_service


_container = None


def get_container() -> "Container":
    """Return the process-wide DI container (one DB pool / broker factory per service)."""
    global _container
    if _container is None:
        _container = Container()
    return _container
