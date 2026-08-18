import os
import json
import redis
import psycopg2
import requests

#psycopg2 (not asyncpg)
#redis-py (not aioredis)
#requests (not aiohttp)
#pika (not aio-pika)

def get_redis():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )


def get_db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "appdb"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "secret"),
    )


def publish_kafka_event(topic, event):
    try:
        requests.post(
            os.getenv("KAFKA_REST_URL", "http://kafka-rest:8082/topics/" + topic),
            json=event,
            timeout=5,
        )
    except Exception:
        pass
