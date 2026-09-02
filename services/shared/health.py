"""Dependency health checks: interface + Postgres/Redis and RabbitMQ checkers."""

from abc import ABC, abstractmethod
from typing import Dict

import redis
from psycopg2 import pool


class HealthChecker(ABC):
    @abstractmethod
    async def check(self) -> Dict[str, bool]:
        """Return {dependency: reachable} for each dependency."""
        ...


class DatabaseHealthChecker(HealthChecker):
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
