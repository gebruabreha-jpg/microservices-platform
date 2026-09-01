"""
Payment Service - Main Application Entry Point.

TRACING:
  - FastAPI auto-instrumentation creates spans for every HTTP request
  - Custom spans track payment processing and Kafka consumption
  - All spans exported via OTLP to Tempo

METRICS:
  - HTTP request duration histogram exported via OTLP
  - RabbitMQ queue depth and processing metrics via OTLP
  - Prometheus /metrics endpoint for direct scraping

LOGGING:
  - Structured JSON logs to stdout (Promtail -> Loki)
  - Includes trace_id/span_id for correlation
"""

import os
import threading
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from app.routes.payment_router import router
from app.service.payment_service import start_kafka_consumer
from shared.tracing import setup_tracing
from shared.logging import get_logger, log_event
from middleware import CorrelationIdMiddleware

# Service identity
os.environ.setdefault("SERVICE_NAME", "payment-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

# =============================================================================
# LOGGING: Structured JSON to stdout -> Promtail -> Loki
# =============================================================================
logger = get_logger("payment-service")

app = FastAPI(title="payment-service")
app.add_middleware(CorrelationIdMiddleware)
app.include_router(router)

setup_tracing(app, os.getenv("SERVICE_NAME"))

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
# HEALTH CHECKS: For K8s liveness/readiness probes
# =============================================================================
@app.get("/health")
async def health():
    """Liveness probe - returns 200 if service is running."""
    return {"status": "ok", "service": "payment-service"}


@app.get("/ready")
async def ready():
    """Readiness probe - returns 200 if service can handle requests."""
    from app.core.database import check_dependencies
    deps = check_dependencies()
    status = "ok" if all(deps.values()) else "degraded"
    return {"status": status, "dependencies": deps}


# =============================================================================
# BACKGROUND CONSUMER: Kafka consumer runs in daemon thread
# =============================================================================
consumer_thread = threading.Thread(target=start_kafka_consumer, daemon=True)
consumer_thread.start()


@app.get("/")
async def root():
    return {"message": "payment API"}


@app.on_event("shutdown")
def shutdown():
    log_event(logger, "info", "Shutting down payment-service")
