"""
Payment Service - Main Application Entry Point.

TRACING:  FastAPI auto-instrumentation + custom spans, exported via OTLP to Tempo.
METRICS:  OpenTelemetry meter, exposed at GET /metrics in Prometheus format.
LOGGING:  Structured JSON to stdout.

Background work (started/stopped by the lifespan handler):
  - Kafka consumer: creates payments from "orders" events
  - Outbox poller:  relays payment_outbox rows to the RabbitMQ "notifications" queue
"""

import os

# Service identity - must be set before importing shared.tracing/metrics, which
# freeze the OpenTelemetry resource (service.name/version) at import time.
os.environ.setdefault("SERVICE_NAME", "payment-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

import threading  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402

from app.container import get_container  # noqa: E402
from app.routes.payment_router import router  # noqa: E402
from app.service.payment_service import start_kafka_consumer  # noqa: E402
from shared.logging import get_logger, log_event  # noqa: E402
from shared.metrics import setup_metrics_endpoint  # noqa: E402
from shared.ratelimit import setup_rate_limiting  # noqa: E402
from shared.tracing import flush_telemetry, setup_tracing  # noqa: E402
from middleware import CorrelationIdMiddleware  # noqa: E402

logger = get_logger("payment-service")

_kafka_consumer_stop = threading.Event()
_background_threads: list[threading.Thread] = []
_outbox_poller = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _outbox_poller

    if os.getenv("DISABLE_BACKGROUND_WORKERS") == "1":
        log_event(logger, "info", "payment-service started (background workers disabled)")
        yield
        return

    _outbox_poller = get_container().get_outbox_poller()
    kafka_thread = threading.Thread(
        target=start_kafka_consumer,
        args=(_kafka_consumer_stop,),
        name="kafka-consumer",
        daemon=True,
    )
    outbox_thread = threading.Thread(
        target=_outbox_poller.run, name="payment-outbox-poller", daemon=True
    )
    for t in (kafka_thread, outbox_thread):
        t.start()
        _background_threads.append(t)
    log_event(logger, "info", "payment-service started")

    try:
        yield
    finally:
        _kafka_consumer_stop.set()
        if _outbox_poller is not None:
            _outbox_poller.stop()
        for t in _background_threads:
            t.join(timeout=5)
        flush_telemetry()
        log_event(logger, "info", "Shutting down payment-service")


app = FastAPI(title="payment-service", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
setup_rate_limiting(app, logger)
app.include_router(router)
setup_tracing(app, os.getenv("SERVICE_NAME"))
setup_metrics_endpoint(app)


@app.get("/health")
async def health():
    """Liveness probe - returns 200 if the process is running."""
    return {"status": "ok", "service": "payment-service"}


@app.get("/ready")
async def ready():
    """Readiness probe - returns 200 if dependencies are reachable."""
    from app.core.database import check_dependencies

    deps = check_dependencies()
    status = "ok" if all(deps.values()) else "degraded"
    return {"status": status, "dependencies": deps}


@app.get("/")
async def root():
    return {"message": "payment API"}
