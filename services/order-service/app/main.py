"""
Order Service - Main Application Entry Point.

Background work (started/stopped by the lifespan handler):
- Outbox poller: relays order_outbox rows to the Kafka "orders" topic

It assembles and starts the application, while other files contain the actual implementations.
main.py
│
├── creates FastAPI
│
├── adds middleware
│
├── adds rate limiting
│
├── adds tracing
│
├── adds routes
│
├── adds metrics
│
└── starts/stops background workers
"""

import os

# Service identity - must be set before importing shared.observability, which
# freeze the OpenTelemetry resource (service.name/version) at import time.
os.environ.setdefault("SERVICE_NAME", "order-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

import threading  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402

from app.container import get_container  # noqa: E402
from app.routes.order_router import router  # noqa: E402
from shared.observability import (  # noqa: E402
    flush_telemetry,
    get_logger,
    setup_metrics_endpoint,
    setup_tracing,
)
from shared.ratelimit import setup_rate_limiting  # noqa: E402
from middleware import CorrelationIdMiddleware  # noqa: E402

logger = get_logger("order-service")

_outbox_poller = None
_background_threads: list[threading.Thread] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _outbox_poller

    if os.getenv("DISABLE_BACKGROUND_WORKERS") == "1":
        logger.info("order-service started (background workers disabled)")
        yield
        return

    _outbox_poller = get_container().get_outbox_poller()
    t = threading.Thread(target=_outbox_poller.run, name="order-outbox-poller", daemon=True)
    t.start()
    _background_threads.append(t)
    logger.info("order-service started")

    try:
        yield
    finally:
        if _outbox_poller is not None:
            _outbox_poller.stop()
        for thread in _background_threads:
            thread.join(timeout=5)
        flush_telemetry()
        logger.info("Shutting down order-service")

#lifespan=lifespanç=When you start and stop, use my lifespan() function.
app = FastAPI(title="order-service", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
setup_rate_limiting(app, logger)
setup_tracing(app, os.getenv("SERVICE_NAME"))
app.include_router(router)
setup_metrics_endpoint(app)


@app.get("/")
async def root():
    return {"message": "order API"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "order-service"}


@app.get("/ready")
async def readiness():
    return {"ready": True}
