"""
Database utilities for Payment Service.

Only contains service-specific utilities.
Connection factories are in shared/factories.py.
"""

import os
import json
import psycopg2
import pika

from shared.config import require_env
from shared.factories import create_db_pool, get_rabbitmq_connection_factory
from resilience import default_retry
from resilience.circuit_breaker import rabbitmq_breaker

# Create connection pool and factory at module level
db_pool = create_db_pool()
rabbitmq_factory = get_rabbitmq_connection_factory()


def get_db():
    """Get database connection from pool or create new one."""
    if db_pool:
        return db_pool.getconn()
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "appdb"),
        user=require_env("POSTGRES_USER"),
        password=require_env("POSTGRES_PASSWORD"),
    )


def release_db(conn):
    """Release connection back to pool or close it."""
    if db_pool:
        db_pool.putconn(conn)
    else:
        conn.close()


def queue_rabbitmq_job(queue, message):
    """Publish message to RabbitMQ queue, guarded by the RabbitMQ circuit breaker.

    ``rabbitmq_breaker.call`` runs the publish and records the outcome, so
    repeated broker failures trip the breaker and fail fast instead of piling
    up blocked connections.
    """
    rabbitmq_breaker.call(_queue_rabbitmq_job_impl, queue, message)


@default_retry
def _queue_rabbitmq_job_impl(queue, message):
    """Internal implementation of RabbitMQ job publishing.

    Topology is provisioned from rabbitmq/definitions.json at broker boot, so
    this does not redeclare the queue.
    """
    connection = rabbitmq_factory()
    channel = connection.channel()
    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()


def check_dependencies():
    """Check health of all dependencies."""
    checks = {}
    conn = None
    try:
        conn = get_db()
        conn.cursor().execute("SELECT 1")
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False
    finally:
        if conn:
            release_db(conn)

    try:
        connection = rabbitmq_factory()
        connection.close()
        checks["rabbitmq"] = True
    except Exception:
        checks["rabbitmq"] = False

    return checks
