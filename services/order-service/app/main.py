"""
Order Service - Main Application Entry Point

Uses Dependency Injection Container to wire dependencies.
"""

import os
from fastapi import FastAPI
from app.routes.order_router import router
from app.container import Container
from shared.tracing import setup_tracing, flush_telemetry
from shared.logging import get_logger, log_event
from middleware import CorrelationIdMiddleware

# Service identity for telemetry
os.environ.setdefault("SERVICE_NAME", "order-service")
os.environ.setdefault("SERVICE_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")

# 1. Logger first
logger = get_logger("order-service")

# Create DI container
container = Container()

# Create app
app = FastAPI(title="order-service")

# Middleware
app.add_middleware(CorrelationIdMiddleware)

# Observability
setup_tracing(app, os.getenv("SERVICE_NAME"))

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
