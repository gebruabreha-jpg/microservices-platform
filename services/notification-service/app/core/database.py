"""
Database utilities for Notification Service.

Only contains service-specific utilities.
Connection factories are in shared/implementations/.
"""

import pika
from shared.implementations import create_db_pool, get_rabbitmq_connection_factory

# Re-export for backward compatibility
__all__ = [
    "create_db_pool",
    "get_rabbitmq_connection_factory",
    "get_rabbitmq_connection",
    "setup_dlq",
]

_rabbitmq_connection_factory = get_rabbitmq_connection_factory()


def get_rabbitmq_connection():
    """Open a new blocking RabbitMQ connection."""
    return _rabbitmq_connection_factory()


def setup_dlq(channel):
    """Setup Dead Letter Exchange and Queue."""
    channel.exchange_declare(exchange="dlx", exchange_type="direct", durable=True)
    channel.queue_declare(queue="dlq", durable=True)
    channel.queue_bind(exchange="dlx", queue="dlq", routing_key="dlq")
