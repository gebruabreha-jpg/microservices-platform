"""
Order Service - Main Application Entry Point

TRACING:
  - FastAPI auto-instrumentation creates spans for every HTTP request
  - Custom spans in service layer track business operations (create_order, etc.)
  - All spans exported via OTLP to Tempo for distributed tracing

METRICS:
  - HTTP request duration histogram exported via OTLP to Prometheus
  - Redis cache hit/miss counters exported via OTLP
  - Prometheus /metrics endpoint still available for direct scraping

LOGGING:
  - Structured JSON logs printed to stdout
  - Collected by Promtail and shipped to Loki
  - Logs include trace_id/span_id for correlation with traces
"""

import os
import logging
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from app.routes.order_router import router
from shared.telemetry import setup_tracing, get_meter, get_logger, log_event

# Service identity for telemetry
os.environ.setdefault("SERVICE_NAME", "order-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

# =============================================================================
# LOGGING: Traditional structured JSON logging (not OTLP)
# =============================================================================
# Logs go to stdout -> Promtail -> Loki
# Each log entry includes service name, timestamp, level, message
logger = get_logger("order-service")

# =============================================================================
# TRACING: Initialize OpenTelemetry tracing
# =============================================================================
# Traces are exported via OTLP to the OTel Collector, then to Tempo.
# FastAPIInstrumentor auto-creates spans for every incoming HTTP request.
setup_tracing(os.getenv("SERVICE_NAME"))

# =============================================================================
# METRICS: OTLP metrics exported to Prometheus via OTel Collector
# =============================================================================
# We use OTLP metrics because:
#   1. Avoids port conflicts in container orchestration
#   2. Background threads (Kafka consumers) can report metrics without HTTP server
#   3. OTel Collector handles aggregation and export to Prometheus
meter = get_meter()
request_counter = meter.create_counter(
    "order_requests_total",
    description="Total order requests",
    unit="1"
)
request_duration = meter.create_histogram(
    "order_request_duration_seconds",
    description="Order request duration in seconds",
    unit="s"
)

# =============================================================================
# FASTAPI APP
# =============================================================================
app = FastAPI(title="order-service")
app.include_router(router)


# =============================================================================
# METRICS ENDPOINT: Prometheus text format (for direct scraping)
# =============================================================================
# This endpoint is kept for Prometheus direct scraping as fallback.
# Primary metrics path is OTLP -> OTel Collector -> Prometheus.
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


@app.get("/")
async def root():
    return {"message": "order API"}


@app.on_event("shutdown")
def shutdown():
    log_event(logger, "info", "Shutting down order-service")
