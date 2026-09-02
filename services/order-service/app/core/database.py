"""
Database utilities for Order Service.

Only contains service-specific utilities.
Connection factories are in shared/factories.py.
"""

from shared.factories import create_db_pool, create_redis_client, create_kafka_producer

# Re-export for backward compatibility
__all__ = ["create_db_pool", "create_redis_client", "create_kafka_producer"]
