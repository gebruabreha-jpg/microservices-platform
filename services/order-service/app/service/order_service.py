"""
Order Service - Business Logic
"""
import json
import uuid
import time
from opentelemetry.trace import Status, StatusCode
from app.repository.order_repository import create_order as create_order_repo, get_all_orders
from app.core.database import get_db, get_redis, publish_kafka_event, release_db, check_dependencies, cache_set, cache_get, cache_delete, db_pool
from app.schema.order_schema import OrderCreate
from shared.tracing import get_tracer
from shared.metrics import get_meteric
from shared.logging import get_logger, log_event

tracer = get_tracer("order-service")

logger = get_logger("order-service")

meteric = get_meteric()
order_counter = meteric.create_counter(
    "order_requests_total",
    description="Total order requests",
    unit="1",
)
order_duration = meter.create_histogram(
    "order_request_duration_seconds",
    description="Order request duration in seconds",
    unit="s",
)
cache_hit_counter = meter.create_counter(
    "order_cache_hits_total",
    description="Cache hits",
    unit="1",
)
cache_miss_counter = meter.create_counter(
    "order_cache_misses_total",
    description="Cache misses",
    unit="1",
)


def health_check():
    deps = check_dependencies()
    status = "ok" if all(deps.values()) else "degraded"
    return {"status": status, "service": "order-service", "dependencies": deps}


def list_orders(limit=20, offset=0):
    cache_key = f"orders:list:{limit}:{offset}"
    cached = cache_get(cache_key)
    if cached:
        cache_hit_counter.add(1)
        return json.loads(cached)

    cache_miss_counter.add(1)
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

    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.customer_id", order.customer_id)
        span.set_attribute("order.product_id", order.product_id)
        span.set_attribute("order.quantity", order.quantity)
        span.set_attribute("order.amount", order.amount)
        span.set_attribute("correlation_id", correlation_id)

        conn = None
        try:
            with tracer.start_as_current_span("db.insert_order") as db_span:
                conn = get_db()
                order_id = create_order_repo(order, conn)
                db_span.set_attribute("db.rows_affected", 1)
                db_span.set_attribute("order.id", order_id)

            with tracer.start_as_current_span("kafka.publish_order_created") as kafka_span:
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
                kafka_span.set_attribute("messaging.system", "kafka")
                kafka_span.set_attribute("messaging.destination", "orders")
                kafka_span.set_attribute("order.id", order_id)

            with tracer.start_as_current_span("redis.cache_order") as cache_span:
                cache_set("order:" + str(order_id), json.dumps(event), ttl=3600)
                _invalidate_list_cache()
                cache_span.set_attribute("cache.operation", "set")
                cache_span.set_attribute("order.id", order_id)

            order_counter.add(1, {"method": "POST", "endpoint": "/orders", "status": "success"})
            log_event(logger, "info", "Order created", order_id=order_id, correlation_id=correlation_id)
            span.set_status(Status(StatusCode.OK))
            return {"id": order_id, "status": order.status, "correlation_id": correlation_id}

        except Exception as e:
            order_counter.add(1, {"method": "POST", "endpoint": "/orders", "status": "error"})
            log_event(logger, "error", "Order creation failed", error=str(e), correlation_id=correlation_id)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            duration = time.time() - start
            order_duration.record(duration, {"endpoint": "/orders"})
            if conn:
                release_db(conn)


def _invalidate_list_cache():
    """Invalidate all list cache entries using SCAN + DELETE."""
    r = get_redis()
    if r:
        for key in r.scan_iter(match="orders:list:*", count=100):
            r.delete(key)
