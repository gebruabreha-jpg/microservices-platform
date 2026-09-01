"""
Dependency Injection Container for Notification Service

Wires together all dependencies following the Dependency Inversion Principle.
"""

import os
import redis
import psycopg2
from psycopg2 import pool
import pika
from typing import Optional, List, Dict, Any

from shared.interfaces import (
    NotificationRepository,
    EventPublisher,
    MetricsClient,
    Logger,
    HealthChecker,
)
from shared.metrics import get_metric
from shared.logging import get_logger, log_event


# =============================================================================
# DATABASE CONNECTIONS
# =============================================================================

def create_db_pool() -> pool.ThreadedConnectionPool:
    """Create PostgreSQL connection pool."""
    try:
        return pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=int(os.getenv("POSTGRES_POOL_SIZE", 10)),
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "appdb"),
            user=os.getenv("POSTGRES_USER", "admin"),
            password=os.getenv("POSTGRES_PASSWORD", "secret"),
        )
    except Exception:
        return None


def get_rabbitmq_connection_factory():
    """Create RabbitMQ connection factory."""
    def factory():
        return pika.BlockingConnection(
            pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
                port=5672,
                credentials=pika.PlainCredentials(
                    os.getenv("RABBITMQ_USER", "admin"),
                    os.getenv("RABBITMQ_PASS", "secret"),
                ),
            )
        )
    return factory


# =============================================================================
# CIRCUIT BREAKERS
# =============================================================================

def create_circuit_breakers():
    """Create circuit breakers for external services."""
    try:
        from resilience import rabbitmq_breaker
        return {
            "rabbitmq": rabbitmq_breaker,
        }
    except ImportError:
        return {
            "rabbitmq": None,
        }


# =============================================================================
# IMPLEMENTATIONS
# =============================================================================

class PostgresNotificationRepository(NotificationRepository):
    """PostgreSQL implementation of NotificationRepository."""

    def __init__(self, db_pool: pool.ThreadedConnectionPool):
        self._db_pool = db_pool

    async def create(self, notification_data: Any) -> int:
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO notifications (type, order_id, status) VALUES (%s, %s, %s) RETURNING id",
                (notification_data.type, notification_data.order_id, notification_data.status),
            )
            notification_id = cur.fetchone()[0]
            conn.commit()
            return notification_id
        finally:
            cur.close()
            self._db_pool.putconn(conn)

    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, type, order_id, status FROM notifications ORDER BY id LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "type": r[1],
                    "order_id": r[2],
                    "status": r[3],
                }
                for r in rows
            ]
        finally:
            cur.close()
            self._db_pool.putconn(conn)


class RabbitMQEventPublisher(EventPublisher):
    """RabbitMQ implementation of EventPublisher."""

    def __init__(self, connection_factory, circuit_breaker=None):
        self._connection_factory = connection_factory
        self._circuit_breaker = circuit_breaker

    async def publish(self, queue: str, event: dict) -> None:
        def _publish():
            connection = self._connection_factory()
            channel = connection.channel()
            channel.queue_declare(queue=queue, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=queue,
                body=json.dumps(event),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            connection.close()

        if self._circuit_breaker:
            with self._circuit_breaker:
                _publish()
        else:
            _publish()


class StructuredLogger(Logger):
    """Structured JSON logger implementation."""

    def __init__(self, service_name: str):
        self._logger = get_logger(service_name)

    def info(self, message: str, **kwargs) -> None:
        log_event(self._logger, "info", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        log_event(self._logger, "error", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        log_event(self._logger, "warning", message, **kwargs)


class RabbitMQHealthChecker(HealthChecker):
    """Health checker for RabbitMQ dependency."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    async def check(self) -> Dict[str, bool]:
        checks = {}
        try:
            connection = self._connection_factory()
            connection.close()
            checks["rabbitmq"] = True
        except Exception:
            checks["rabbitmq"] = False
        return checks


# =============================================================================
# DI CONTAINER
# =============================================================================

class Container:
    """Dependency Injection Container."""

    def __init__(self):
        # Infrastructure
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
