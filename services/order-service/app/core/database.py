"""
Database connections and utilities.

Only contains connection factories - no business logic.
All repository implementations are in the DI container.
"""

import os
import json
import redis
import psycopg2
from psycopg2 import pool
from kafka import KafkaProducer
import pika


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
# RABBITMQ UTILITIES
# =============================================================================

def setup_dlq(channel):
    """Setup Dead Letter Exchange and Queue."""
    channel.exchange_declare(exchange="dlx", exchange_type="direct", durable=True)
    channel.queue_declare(queue="dlq", durable=True)
    channel.queue_bind(exchange="dlx", queue="dlq", routing_key="dlq")
