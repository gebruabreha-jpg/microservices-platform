"""
Notification Service - Main Application Entry Point.

Background work (started/stopped by the lifespan handler):
  - RabbitMQ consumer for the "notifications" queue
  - DLQ consumer for dead-lettered messages
"""

import os

# Service identity - must be set before importing shared.observability, which
# freeze the OpenTelemetry resource (service.name/version) at import time.
os.environ.setdefault("SERVICE_NAME", "notification-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

import threading  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402

from app.container import get_container  # noqa: E402
from app.routes.notification_router import router  # noqa: E402
from shared.observability import (  # noqa: E402
    flush_telemetry,
    get_logger,
    setup_metrics_endpoint,
    setup_tracing,
)
from shared.ratelimit import setup_rate_limiting  # noqa: E402
from middleware import CorrelationIdMiddleware  # noqa: E402

logger = get_logger("notification-service")

_consumer_service = None
_background_threads: list[threading.Thread] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_service

    if os.getenv("DISABLE_BACKGROUND_WORKERS") == "1":
        logger.info("notification-service started (background workers disabled)")
        yield
        return

    _consumer_service = get_container().get_notification_service()
    for target, name in (
        (_consumer_service.start_consumer, "notifications-consumer"),
        (_consumer_service.start_dlq_consumer, "dlq-consumer"),
    ):
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        _background_threads.append(t)
    logger.info("notification-service started")

    try:
        yield
    finally:
        if _consumer_service is not None:
            _consumer_service.stop()
        for t in _background_threads:
            t.join(timeout=5)
        flush_telemetry()
        logger.info("Shutting down notification-service")


app = FastAPI(title="notification-service", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
setup_rate_limiting(app, logger)
setup_tracing(app, os.getenv("SERVICE_NAME"))
app.include_router(router)
setup_metrics_endpoint(app)


@app.get("/")
async def root():
    return {"message": "notification API"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification-service"}


@app.get("/ready")
async def readiness():
    return {"ready": True}
