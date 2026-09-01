import os
import json
import pika
import psycopg2
from psycopg2 import pool

from resilience import default_retry
from resilience.circuit_breaker import rabbitmq_breaker

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


def setup_dlq(channel):
    channel.exchange_declare(exchange="dlx", exchange_type="direct", durable=True)
    channel.queue_declare(queue="dlq", durable=True)
    channel.queue_bind(exchange="dlx", queue="dlq", routing_key="dlq")


def queue_rabbitmq_job(queue, message):
    if rabbitmq_breaker:
        with rabbitmq_breaker:
            queue_rabbitmq_job_impl(queue, message)
    else:
        queue_rabbitmq_job_impl(queue, message)


@default_retry
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
        connection = get_rabbitmq_connection()
        connection.close()
        checks["rabbitmq"] = True
    except Exception:
        checks["rabbitmq"] = False

    return checks
