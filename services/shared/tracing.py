"""
Order Service - Main Application Entry Point

Responsibilities:
- Create FastAPI app
- Register middleware (correlation ID, rate limiting)
- Set up observability (tracing, metrics, logging)
- Include routes
"""

import os
from fastapi import FastAPI
from app.routes.order_router import router
from shared.tracing import setup_tracing, flush_telemetry
from shared.metrics import get_meter
from shared.logging import get_logger, log_event
from middleware import CorrelationIdMiddleware

# Service identity for telemetry
os.environ.setdefault("SERVICE_NAME", "order-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

logger = get_logger("order-service")

# Create app
app = FastAPI(title="order-service")

# Middleware
app.add_middleware(CorrelationIdMiddleware)

# Rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_ipaddr
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_ipaddr, default_limits=["100/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    logger.warning("slowapi not installed, rate limiting disabled")

# Observability
setup_tracing(app, os.getenv("SERVICE_NAME"))

# Metrics - basic HTTP request metrics
meter = get_meter()
request_counter = meter.create_counter(
    "http_requests_total",
    description="Total HTTP requests",
    unit="1",
)
request_duration = meter.create_histogram(
    "http_request_duration_seconds",
    description="HTTP request duration in seconds",
    unit="s",
)

# Routes
app.include_router(router)


@app.get("/")
async def root():
    return {"message": "order API"}


@app.on_event("shutdown")
def shutdown():
    log_event(logger, "info", "Shutting down order-service")
    flush_telemetry()