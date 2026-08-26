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
import uuid
import logging
from fastapi import FastAPI, Response, Request
from fastapi.responses import PlainTextResponse
from app.routes.order_router import router
from shared.telemetry import setup_tracing, get_meter, get_logger, log_event

# Service identity for telemetry
os.environ.setdefault("SERVICE_NAME", "order-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

logger = get_logger("order-service")

#Create app
app = FastAPI(title="order-service")

#Add correlation ID middleware
"""
Middleware to add a correlation ID to each request for tracing/logging correlation.
If the client provides a 'X-Correlation-ID' header, use that; otherwise, generate a new UUID.
"""
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    response: Response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    logger.info(f"{request.method} {request.url.path}", extra={"correlation_id": correlation_id})
    return response

# set up Rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_ipaddr
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_ipaddr, default_limits=["100/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    logger.warning("slowapi not installed,rate limiting middleware will not be available. Install slowapi to enable rate limiting.")

#set up tracing
#instrumentation to captures router spans properly
setup_tracing(app, os.getenv("SERVICE_NAME"))
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

#Include router
app.include_router(router)

#Add metrics endpoint
# METRICS ENDPOINT: Prometheus text format (for direct scraping)
# This endpoint is kept for Prometheus direct scraping as fallback.
# Primary metrics path is OTLP -> OTel Collector -> Prometheus.
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    @app.get("/metrics")
    async def metrics_prometheus():
        """Return Prometheus-formatted metrics for direct scraping."""
        return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
except ImportError:
    logger.warning("prometheus_client not installed, /metrics endpoint will not be available. Install prometheus_client to enable Prometheus metrics endpoint.")



@app.get("/")
async def root():
    return {"message": "order API"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/ready")
async def readiness():
    # Add checks for dependencies (DB, Redis, etc.)
    return {"ready": True}

@app.on_event("shutdown")
def shutdown():
    log_event(logger, "info", "Shutting down order-service")
    # Force flush before shutdown
    from opentelemetry.sdk.trace import get_tracer_provider
    get_tracer_provider().force_flush()