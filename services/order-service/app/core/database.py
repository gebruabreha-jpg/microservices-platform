import os
import json
import logging
import redis
import psycopg2
from psycopg2 import pool
from kafka import KafkaProducer
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
    from shared.circuit_breaker import redis_breaker, kafka_breaker
except ImportError:
    redis_breaker = None
    kafka_breaker = None

logger = logging.getLogger("order-service")

SERVICE_NAME = "order-service"

try:
    from prometheus_client import Counter, Histogram, CollectorRegistry
    registry = CollectorRegistry()
    REQUEST_COUNT = Counter("order_requests_total", "Total order requests", ["method", "endpoint", "status"], registry=registry)
    REQUEST_LATENCY = Histogram("order_request_latency_seconds", "Order request latency", ["endpoint"], registry=registry)
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

try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )
    redis_client.ping()
except Exception:
    redis_client = None

try:
    kafka_producer = KafkaProducer(
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        retries=3,
        acks="all",
    )
except Exception:
    kafka_producer = None


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


def get_redis():
    return redis_client


def publish_kafka_event(topic, event):
    if kafka_breaker:
        publish_kafka_event_impl(topic, event)
    else:
        publish_kafka_event_impl(topic, event)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def publish_kafka_event_impl(topic, event):
    if not kafka_producer:
        raise RuntimeError("Kafka producer not available")
    kafka_producer.send(topic, event)
    kafka_producer.flush(timeout=5)


def cache_set(key, value, ttl=3600):
    r = get_redis()
    if r:
        r.set(key, value, ex=ttl)


def cache_get(key):
    r = get_redis()
    if r:
        return r.get(key)
    return None


def cache_delete(key):
    r = get_redis()
    if r:
        r.delete(key)


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
        r = get_redis()
        r.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    return checks
