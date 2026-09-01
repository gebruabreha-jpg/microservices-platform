"""
Shared implementations for all services.

Contains concrete implementations of interfaces that can be reused
across multiple services, following DRY principle.
"""

import os
import json
import redis
import psycopg2
from psycopg2 import pool
from kafka import KafkaProducer
import pika
from typing import Optional, Dict

from shared.interfaces import (
    CacheClient,
    EventPublisher,
    Logger,
    HealthChecker,
)
from shared.metrics import get_metric
from shared.logging import get_logger, log_event


# =============================================================================
# CONNECTION FACTORIES
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


def create_redis_client() -> redis.Redis:
    """Create Redis client."""
    try:
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=True,
        )
        client.ping()
        return client
    except Exception:
        return None


def create_kafka_producer() -> KafkaProducer:
    """Create Kafka producer."""
    try:
        return KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            retries=3,
            acks="all",
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
    """Create circuit breakers for all external services."""
    try:
        from resilience import kafka_breaker, rabbitmq_breaker, redis_breaker
        return {
            "kafka": kafka_breaker,
            "rabbitmq": rabbitmq_breaker,
            "redis": redis_breaker,
        }
    except ImportError:
        return {
            "kafka": None,
            "rabbitmq": None,
            "redis": None,
        }


# =============================================================================
# CACHE IMPLEMENTATION
# =============================================================================

class RedisCacheClient(CacheClient):
    """Redis implementation of CacheClient."""

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        self._redis.set(key, value, ex=ttl)

    def get(self, key: str) -> Optional[str]:
        return self._redis.get(key)

    def delete(self, key: str) -> None:
        self._redis.delete(key)

    def delete_pattern(self, pattern: str) -> None:
        for key in self._redis.scan_iter(match=pattern, count=100):
            self._redis.delete(key)


# =============================================================================
# EVENT PUBLISHER IMPLEMENTATIONS
# =============================================================================

class KafkaEventPublisher(EventPublisher):
    """Kafka implementation of EventPublisher."""

    def __init__(self, kafka_producer: KafkaProducer, circuit_breaker=None):
        self._producer = kafka_producer
        self._circuit_breaker = circuit_breaker

    async def publish(self, topic: str, event: dict) -> None:
        if self._circuit_breaker:
            with self._circuit_breaker:
                self._producer.send(topic, event)
                self._producer.flush(timeout=5)
        else:
            self._producer.send(topic, event)
            self._producer.flush(timeout=5)


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


# =============================================================================
# LOGGER IMPLEMENTATION
# =============================================================================

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


# =============================================================================
# HEALTH CHECKER IMPLEMENTATIONS
# =============================================================================

class DatabaseHealthChecker(HealthChecker):
    """Health checker for database dependencies."""

    def __init__(self, db_pool: pool.ThreadedConnectionPool, redis_client: redis.Redis = None):
        self._db_pool = db_pool
        self._redis_client = redis_client

    async def check(self) -> Dict[str, bool]:
        checks = {}
        conn = None
        try:
            conn = self._db_pool.getconn()
            conn.cursor().execute("SELECT 1")
            checks["postgres"] = True
        except Exception:
            checks["postgres"] = False
        finally:
            if conn:
                self._db_pool.putconn(conn)

        if self._redis_client:
            try:
                self._redis_client.ping()
                checks["redis"] = True
            except Exception:
                checks["redis"] = False

        return checks


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
