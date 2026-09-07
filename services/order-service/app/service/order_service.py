"""
Order Service - Business Logic (OOP + DI)

Swappable deps (repo/cache/publisher/health) are constructor-injected;
logging/metrics/tracing are ambient (module-level, not injected).
"""

import json
import time
import uuid
from typing import Optional, List, Dict
from opentelemetry.trace import Status, StatusCode

from shared.cache import CacheClient
from shared.events import EventPublisher
from shared.health import HealthChecker
from shared.repository import OrderRepository
from shared.observability import get_metric, get_service_telemetry


class OrderService:
    """Order business logic. Swappable dependencies (repo/cache/publisher/health)
    are injected; logging/metrics/tracing are ambient infrastructure."""

    def __init__(
        self,
        order_repository: OrderRepository,
        cache: CacheClient,
        event_publisher: EventPublisher,
        health_checker: HealthChecker,
    ):
        self._order_repository = order_repository
        self._cache = cache
        self._event_publisher = event_publisher
        self._health_checker = health_checker
        telemetry = get_service_telemetry("order-service", "order", "order")
        self._logger = telemetry.logger
        self._tracer = telemetry.tracer
        self._order_counter = telemetry.request_counter
        self._order_duration = telemetry.request_duration

        metrics = get_metric()
        self._cache_hit_counter = metrics.create_counter(
            "order_cache_hits_total",
            description="Cache hits",
            unit="1",
        )
        self._cache_miss_counter = metrics.create_counter(
            "order_cache_misses_total",
            description="Cache misses",
            unit="1",
        )

    async def health_check(self) -> Dict:
        """Check service health."""
        deps = await self._health_checker.check()
        status = "ok" if all(deps.values()) else "degraded"
        return {"status": status, "service": "order-service", "dependencies": deps}

    async def create_order(self, order_data, request_id: Optional[str] = None) -> Dict:
        """Create a new order."""
        start = time.time()
        correlation_id = request_id or str(uuid.uuid4())

        with self._tracer.start_as_current_span("create_order") as span:
            span.set_attribute("order.customer_id", order_data.customer_id)
            span.set_attribute("order.product_id", order_data.product_id)
            span.set_attribute("correlation_id", correlation_id)

            def build_event(new_order_id):
                return "orders", {
                    "order_id": new_order_id,
                    "customer_id": order_data.customer_id,
                    "product_id": order_data.product_id,
                    "quantity": order_data.quantity,
                    "amount": order_data.amount,
                    "status": order_data.status,
                    "correlation_id": correlation_id,
                }

            try:
                # Database write + outbox event, atomically. The "orders" event
                # is relayed to Kafka by the outbox poller, so it cannot be lost
                # if the broker is briefly unavailable.
                with self._tracer.start_as_current_span("db.insert_order") as db_span:
                    order_id = await self._order_repository.create(
                        order_data, outbox_event=build_event
                    )
                    db_span.set_attribute("order.id", order_id)

                order_view = {
                    "id": order_id,
                    "customer_id": order_data.customer_id,
                    "product_id": order_data.product_id,
                    "quantity": order_data.quantity,
                    "amount": order_data.amount,
                    "status": order_data.status,
                }

                # Cache operation
                with self._tracer.start_as_current_span("redis.cache_order") as cache_span:
                    self._cache.set(f"order:{order_id}", json.dumps(order_view), ttl=3600)
                    self._cache.delete_pattern("orders:list:*")
                    cache_span.set_attribute("cache.operation", "set")

                # Record metrics
                self._order_counter.add(1, {"method": "POST", "endpoint": "/orders", "status": "success"})
                self._logger.info("Order created", order_id=order_id, correlation_id=correlation_id)
                span.set_status(Status(StatusCode.OK))

                return {**order_view, "correlation_id": correlation_id}

            except Exception as e:
                self._order_counter.add(1, {"method": "POST", "endpoint": "/orders", "status": "error"})
                self._logger.error("Order creation failed", error=str(e), correlation_id=correlation_id)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start
                self._order_duration.record(duration, {"endpoint": "/orders"})

    async def get_order(self, order_id: int) -> Optional[Dict]:
        """Return one order (cache-first), or None if it does not exist."""
        cached = self._cache.get(f"order:{order_id}")
        if cached:
            self._cache_hit_counter.add(1)
            return json.loads(cached)

        self._cache_miss_counter.add(1)
        order = await self._order_repository.get_by_id(order_id)
        if order is not None:
            self._cache.set(f"order:{order_id}", json.dumps(order), ttl=3600)
        return order

    async def list_orders(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """List orders with pagination."""
        cache_key = f"orders:list:{limit}:{offset}"
        cached = self._cache.get(cache_key)

        if cached:
            self._cache_hit_counter.add(1)
            return json.loads(cached)

        self._cache_miss_counter.add(1)
        rows = await self._order_repository.get_all(limit=limit, offset=offset)
        self._cache.set(cache_key, json.dumps(rows), ttl=60)
        return rows
