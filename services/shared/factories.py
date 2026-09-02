"""
Connection factories for infrastructure clients.

Credentials come from the environment with no baked-in default (see
``require_env``); a genuine connection failure returns None so callers can
start degraded and retry.
"""

import json
import os

import pika
import redis
from kafka import KafkaProducer
from psycopg2 import pool

from shared.config import require_env


def create_db_pool() -> pool.ThreadedConnectionPool:
    user = require_env("POSTGRES_USER")
    password = require_env("POSTGRES_PASSWORD")
    try:
        return pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=int(os.getenv("POSTGRES_POOL_SIZE", "10")),
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "appdb"),
            user=user,
            password=password,
        )
    except Exception:
        return None


def create_redis_client() -> redis.Redis:
    try:
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=True,
        )
        client.ping()
        return client
    except Exception:
        return None


def create_kafka_producer() -> KafkaProducer:
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
    user = require_env("RABBITMQ_USER")
    password = require_env("RABBITMQ_PASS")

    def factory():
        return pika.BlockingConnection(
            pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
                port=int(os.getenv("RABBITMQ_PORT", "5672")),
                credentials=pika.PlainCredentials(user, password),
            )
        )

    return factory


def create_circuit_breakers() -> dict:
    """Return {name: breaker} for external dependencies, or None values if the
    resilience package is unavailable."""
    try:
        from resilience import kafka_breaker, rabbitmq_breaker, redis_breaker

        return {"kafka": kafka_breaker, "rabbitmq": rabbitmq_breaker, "redis": redis_breaker}
    except ImportError:
        return {"kafka": None, "rabbitmq": None, "redis": None}
