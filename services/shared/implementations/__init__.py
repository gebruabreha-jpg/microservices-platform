"""
Concrete implementations of interfaces.
"""

import json
import os
import redis
import psycopg2
from psycopg2 import pool
from kafka import KafkaProducer
import pika
from typing import Optional, List, Dict, Any

from shared.interfaces import (
    OrderRepository,
    NotificationRepository,
    CacheClient,
    EventPublisher,
    Logger,
    HealthChecker,
)
from shared.metrics import get_metric
from shared.logging import get_logger, log_event


# =============================================================================
# REPOSITORY IMPLEMENTATIONS
# =============================================================================

class PostgresOrderRepository(OrderRepository):
    """PostgreSQL implementation of OrderRepository."""

    def __init__(self, db_pool: pool.ThreadedConnectionPool):
        self._db_pool = db_pool

    async def create(self, order_data: Any) -> int:
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO orders (customer_id, product_id, quantity, amount, status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (order_data.customer_id, order_data.product_id, order_data.quantity, order_data.amount, order_data.status),
            )
            order_id = cur.fetchone()[0]
            conn.commit()
            return order_id
        finally:
            cur.close()
            self._db_pool.putconn(conn)

    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        conn = self._db_pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, customer_id, product_id, quantity, amount, status FROM orders ORDER BY id LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "customer_id": r[1],
                    "product_id": r[2],
                    "quantity": r[3],
                    "amount": float(r[4]),
                    "status": r[5],
                }
                for r in rows
            ]
        finally:
            cur.close()
            self._db_pool.putconn(conn)


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
        self._service_name = service_name

    def info(self, message: str, **kwargs) -> None:
        log_event(self._logger, "info", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        log_event(self._logger, "error", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        log_event(self._logger, "warning", message, **kwargs)


# =============================================================================
# HEALTH CHECKER IMPLEMENTATION
# =============================================================================

class DatabaseHealthChecker(HealthChecker):
    """Health checker for database dependencies."""

    def __init__(self, db_pool: pool.ThreadedConnectionPool, redis_client: redis.Redis):
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
