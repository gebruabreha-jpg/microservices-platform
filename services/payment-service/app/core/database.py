import os
import json
import logging
import pika
import psycopg2
from psycopg2 import pool
try:
    from tenacity import retry, stop_after_attempt, wait_exponential
except ImportError:
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def stop_after_attempt(x):
        return None
    def wait_exponential(**kwargs):
        return None
from shared.logger import log_event
from shared.telemetry import setup_tracing

try:
    from shared.circuit_breaker import rabbitmq_breaker
except ImportError:
    rabbitmq_breaker = None

logger = logging.getLogger("payment-service")

SERVICE_NAME = "payment-service"

try:
    from prometheus_client import Counter, Histogram, CollectorRegistry
    registry = CollectorRegistry()
    REQUEST_COUNT = Counter("payment_requests_total", "Total payment requests", ["method", "endpoint", "status"], registry=registry)
    REQUEST_LATENCY = Histogram("payment_request_latency_seconds", "Payment request latency", ["endpoint"], registry=registry)
except ImportError:
    REQUEST_COUNT = None
    REQUEST_LATENCY = None

try:
    db_pool = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=int(os.getenv("POSTGRES_POOL_SIZE", 10)),
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "appdb"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "secret"),
    )
except Exception:
    db_pool = None


def get_db():
    if db_pool:
        return db_pool.getconn()
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "appdb"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "secret"),
    )


def release_db(conn):
    if db_pool:
        db_pool.putconn(conn)
    else:
        conn.close()


def get_rabbitmq_connection():
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


def queue_rabbitmq_job(queue, message):
    if rabbitmq_breaker:
        queue_rabbitmq_job_impl(queue, message)
    else:
        queue_rabbitmq_job_impl(queue, message)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def queue_rabbitmq_job_impl(queue, message):
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()


def check_dependencies():
    checks = {}
    try:
        conn = get_db()
        conn.cursor().execute("SELECT 1")
        conn.close()
        if db_pool:
            release_db(conn)
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False

    try:
        connection = get_rabbitmq_connection()
        connection.close()
        checks["rabbitmq"] = True
    except Exception:
        checks["rabbitmq"] = False

    return checks
