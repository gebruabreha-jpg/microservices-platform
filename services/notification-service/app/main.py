"""
Notification Service - Main Application Entry Point

TRACING:
  - FastAPI auto-instrumentation creates spans for every HTTP request
  - Custom spans track notification sending and RabbitMQ consumption
  - All spans exported via OTLP to Tempo

METRICS:
  - HTTP request duration histogram exported via OTLP
  - DLQ message counter exported via OTLP
  - Prometheus /metrics endpoint for direct scraping

LOGGING:
  - Structured JSON logs to stdout (Promtail -> Loki)
  - Includes trace_id/span_id for correlation with traces
"""

import os
import logging
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from app.routes.notification_router import router
import threading
from app.service.notification_service import start_consumer, start_dlq_consumer
from shared.telemetry import setup_tracing, get_meter, get_logger, log_event

# Service identity
os.environ.setdefault("SERVICE_NAME", "notification-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

# =============================================================================
# LOGGING: Structured JSON to stdout -> Promtail -> Loki
# =============================================================================
logger = get_logger("notification-service")

app = FastAPI(title="notification-service")
app.include_router(router)

setup_tracing(app, os.getenv("SERVICE_NAME"))

# =============================================================================
# METRICS: OTLP metrics -> Prometheus (via OTel Collector)
# =============================================================================
meter = get_meter()
request_counter = meter.create_counter(
    "notification_requests_total",
    description="Total notification requests",
    unit="1"
)
request_duration = meter.create_histogram(
    "notification_request_duration_seconds",
    description="Notification request duration in seconds",
    unit="s"
)
dlq_counter = meter.create_counter(
    "notification_dlq_total",
    description="Messages sent to DLQ"
)

# =============================================================================
# FASTAPI APP
# =============================================================================
app = FastAPI(title="notification-service")
app.include_router(router)


# =============================================================================
# METRICS ENDPOINT: Prometheus text format
# =============================================================================
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    @app.get("/metrics")
    async def metrics_prometheus():
        """Return Prometheus-formatted metrics for direct scraping."""
        return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
except ImportError:
    pass


# =============================================================================
# RATE LIMITING
# =============================================================================
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_ipaddr
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_ipaddr, default_limits=["100/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    pass


# =============================================================================
# BACKGROUND CONSUMERS: RabbitMQ consumers run in daemon threads
# =============================================================================
consumer_thread = threading.Thread(target=start_consumer, daemon=True)
consumer_thread.start()

dlq_thread = threading.Thread(target=start_dlq_consumer, daemon=True)
dlq_thread.start()


@app.get("/")
async def root():
    return {"message": "notification API"}


@app.on_event("shutdown")
def shutdown():
    log_event(logger, "info", "Shutting down notification-service")
