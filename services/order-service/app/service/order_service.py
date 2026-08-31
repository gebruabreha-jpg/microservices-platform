"""
Order Service - Business Logic

TRACING:
  Custom spans wrap each business operation to trace:
  - Database operations (insert, select)
  - Cache operations (Redis get/set/delete)
  - Event publishing (Kafka produce)

METRICS:
  - order_requests_total counter (OTLP)
  - order_request_duration_seconds histogram (OTLP)
  - order_cache_hits_total counter (OTLP)
  - order_cache_misses_total counter (OTLP)

LOGGING:
  Structured JSON logs with trace_id/span_id for correlation.
"""

import json
import uuid
import time
from prometheus_client import Counter, Histogram
from opentelemetry.trace import Status, StatusCode
from app.repository.order_repository import create_order as create_order_repo, get_all_orders
from app.core.database import get_db, get_redis, publish_kafka_event, release_db, check_dependencies, cache_set, cache_get, cache_delete, db_pool
from app.schema.order_schema import OrderCreate
from shared.tracing import get_tracer
from shared.metrics import get_meter
from shared.logging import get_logger, log_event

# =============================================================================
# TRACING: Get tracer for custom spans
# =============================================================================
tracer = get_tracer("order-service")
logger = get_logger("order-service")

# =============================================================================
# METRICS: OTLP metrics (primary path) + Prometheus client (fallback)
# =============================================================================
# Primary: OTLP metrics exported every 15s via OTel Collector
# Fallback: prometheus_client for direct /metrics scraping
meter = get_meter()

try:
    otlp_request_count = meter.create_counter(
        "order_requests_total",
        description="Total order requests",
        unit="1"
    )
    otlp_request_duration = meter.create_histogram(
        "order_request_duration_seconds",
        description="Order request duration in seconds",
        unit="s"
    )
    otlp_cache_hit = meter.create_counter(
        "order_cache_hits_total",
        description="Cache hits",
        unit="1"
    )
    otlp_cache_miss = meter.create_counter(
        "order_cache_misses_total",
        description="Cache misses",
        unit="1"
    )

    # Fallback Prometheus metrics (used by /metrics endpoint)
    prometheus_registry = None
    REQUEST_COUNT = Counter("order_requests_total", "Total order requests", ["method", "endpoint", "status"])
    REQUEST_LATENCY = Histogram("order_request_latency_seconds", "Order request latency", ["endpoint"])
    CACHE_HIT = Counter("order_cache_hits_total", "Cache hits")
    CACHE_MISS = Counter("order_cache_misses_total", "Cache misses")
except ImportError:
    otlp_request_count = None
    otlp_request_duration = None
    otlp_cache_hit = None
    otlp_cache_miss = None
    REQUEST_COUNT = None
    REQUEST_LATENCY = None
    CACHE_HIT = None
    CACHE_MISS = None


# =============================================================================
# HEALTH CHECK
# =============================================================================
def health_check():
    deps = check_dependencies()
    status = "ok" if all(deps.values()) else "degraded"
    return {"status": status, "service": "order-service", "dependencies": deps}


# =============================================================================
# LEGACY METRICS (kept for backward compatibility with /metrics endpoint)
# =============================================================================
def get_metrics():
    r = get_redis()
    count = r.incr("orders_requests_total") if r else 0
    return {"orders_requests_total": count}


# =============================================================================
# ORDER OPERATIONS
# =============================================================================
def list_orders(limit=20, offset=0):
    cache_key = f"orders:list:{limit}:{offset}"
    cached = cache_get(cache_key)
    if cached:
        if otlp_cache_hit:
            otlp_cache_hit.add(1)
        if CACHE_HIT:
            CACHE_HIT.inc()
        return json.loads(cached)

    if otlp_cache_miss:
        otlp_cache_miss.add(1)
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

    # =========================================================================
    # TRACING: Custom span for order creation business logic
    # =========================================================================
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.customer_id", order.customer_id)
        span.set_attribute("order.product_id", order.product_id)
        span.set_attribute("order.quantity", order.quantity)
        span.set_attribute("order.amount", order.amount)
        span.set_attribute("correlation_id", correlation_id)

        try:
            # =========================================================================
            # TRACING: Database operation span
            # =========================================================================
            with tracer.start_as_current_span("db.insert_order") as db_span:
                conn = get_db()
                order_id = create_order_repo(order, conn)
                db_span.set_attribute("db.rows_affected", 1)
                db_span.set_attribute("order.id", order_id)

            # =========================================================================
            # TRACING: Kafka event publish span
            # =========================================================================
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

            # =========================================================================
            # TRACING: Cache operation span
            # =========================================================================
            with tracer.start_as_current_span("redis.cache_order") as cache_span:
                cache_set("order:" + str(order_id), json.dumps(event), ttl=3600)
                cache_delete("orders:list:*")
                cache_span.set_attribute("cache.operation", "set")
                cache_span.set_attribute("order.id", order_id)

            # =========================================================================
            # METRICS: Record success
            # =========================================================================
            if otlp_request_count:
                otlp_request_count.add(1, {"method": "POST", "endpoint": "/orders", "status": "success"})
            if REQUEST_COUNT:
                REQUEST_COUNT.labels(method="POST", endpoint="/orders", status="success").inc()

            log_event(logger, "info", "Order created", order_id=order_id, correlation_id=correlation_id)
            span.set_status(Status(StatusCode.OK))
            return {"id": order_id, "status": order.status, "correlation_id": correlation_id}

        except Exception as e:
            # =========================================================================
            # METRICS: Record failure
            # =========================================================================
            if otlp_request_count:
                otlp_request_count.add(1, {"method": "POST", "endpoint": "/orders", "status": "error"})
            if REQUEST_COUNT:
                REQUEST_COUNT.labels(method="POST", endpoint="/orders", status="error").inc()

            log_event(logger, "error", "Order creation failed", error=str(e), correlation_id=correlation_id)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            # =========================================================================
            # METRICS: Record duration
            # =========================================================================
            duration = time.time() - start
            if otlp_request_duration:
                otlp_request_duration.record(duration, {"endpoint": "/orders"})
            if REQUEST_LATENCY:
                REQUEST_LATENCY.labels(endpoint="/orders").observe(duration)
            if db_pool and 'conn' in locals():
                release_db(conn)
