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
from shared.metrics import get_metric
from shared.logging import get_logger, log_event
from middleware import CorrelationIdMiddleware

# Service identity for telemetry
os.environ.setdefault("SERVICE_NAME", "order-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

#If tracing/metrics setup fails, we need logging to debug it 
#so that is whywe put first the logger setup
# ═══════════════════════════════════════════════════════════════
# 1. LOGGER FIRST — so you can log any setup errors below
# ═══════════════════════════════════════════════════════════════
logger = get_logger("order-service")

# Create app
app = FastAPI(title="order-service")

# Middleware
app.add_middleware(CorrelationIdMiddleware)

# Observability initialization
# ═══════════════════════════════════════════════════════════════
# 2. TRACING SECOND — instrument the app
# ═══════════════════════════════════════════════════════════════
setup_tracing(app, os.getenv("SERVICE_NAME"))


# ═══════════════════════════════════════════════════════════════
# 3. METRICS THIRD — create metric instruments
# ═══════════════════════════════════════════════════════════════
metric = get_metric()
request_counter = metric.create_counter(
    "http_requests_total",
    description="Total HTTP requests",
    unit="1",
)
request_duration = metric.create_histogram(
    "http_request_duration_seconds",
    description="HTTP request duration in seconds",
    unit="s",
)

# Routes
app.include_router(router)


@app.get("/")
async def root():
    return {"message": "order API"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def readiness():
    return {"ready": True}


@app.on_event("shutdown")
def shutdown():
    log_event(logger, "info", "Shutting down order-service")
    flush_telemetry()