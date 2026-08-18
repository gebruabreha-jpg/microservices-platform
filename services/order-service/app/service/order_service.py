import json
import uuid
import time
from prometheus_client import Counter, Histogram, CollectorRegistry
from app.repository.order_repository import create_order, get_all_orders
from app.core.database import get_redis, publish_kafka_event, release_db, check_dependencies, cache_set, cache_get, cache_delete
from app.schema.order_schema import OrderCreate

try:
    from prometheus_client import Counter, Histogram, CollectorRegistry
    registry = CollectorRegistry()
    REQUEST_COUNT = Counter("order_requests_total", "Total order requests", ["method", "endpoint", "status"], registry=registry)
    REQUEST_LATENCY = Histogram("order_request_latency_seconds", "Order request latency", ["endpoint"], registry=registry)
    CACHE_HIT = Counter("order_cache_hits_total", "Cache hits", registry=registry)
    CACHE_MISS = Counter("order_cache_misses_total", "Cache misses", registry=registry)
except ImportError:
    REQUEST_COUNT = None
    REQUEST_LATENCY = None
    CACHE_HIT = None
    CACHE_MISS = None


def health_check():
    deps = check_dependencies()
    status = "ok" if all(deps.values()) else "degraded"
    return {"status": status, "service": "order-service", "dependencies": deps}


def get_metrics():
    r = get_redis()
    count = r.incr("orders_requests_total") if r else 0
    return {"orders_requests_total": count}


def list_orders(limit=20, offset=0):
    cache_key = f"orders:list:{limit}:{offset}"
    cached = cache_get(cache_key)
    if cached:
        if CACHE_HIT:
            CACHE_HIT.inc()
        return json.loads(cached)

    if CACHE_MISS:
        CACHE_MISS.inc()
    rows = get_all_orders(limit=limit, offset=offset)
    result = [
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
    cache_set(cache_key, json.dumps(result), ttl=60)
    return result


def create_order(order: OrderCreate, request_id=None):
    start = time.time()
    correlation_id = request_id or str(uuid.uuid4())
    try:
        conn = get_db()
        order_id = create_order(order, conn)
        event = {
            "order_id": order_id,
            "customer_id": order.customer_id,
            "product_id": order.product_id,
            "quantity": order.quantity,
            "amount": order.amount,
            "status": order.status,
            "correlation_id": correlation_id,
        }
        publish_kafka_event("orders", event)
        cache_set("order:" + str(order_id), json.dumps(event), ttl=3600)
        cache_delete("orders:list:*")
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method="POST", endpoint="/orders", status="success").inc()
        log_event(logger, "info", "Order created", order_id=order_id, correlation_id=correlation_id)
        return {"id": order_id, "status": order.status, "correlation_id": correlation_id}
    except Exception as e:
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method="POST", endpoint="/orders", status="error").inc()
        log_event(logger, "error", "Order creation failed", error=str(e), correlation_id=correlation_id)
        raise
    finally:
        if REQUEST_LATENCY:
            REQUEST_LATENCY.labels(endpoint="/orders").observe(time.time() - start)
        if db_pool:
            release_db(conn)
