"""
Order Service - API Routes
METRICS ENDPOINT:
  Returns Prometheus text format for direct scraping.
  Primary metrics path is OTLP -> OTel Collector -> Prometheus.
"""

import uuid
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from app.service.order_service import health_check, list_orders, create_order
from app.schema.order_schema import OrderCreate

router = APIRouter()
@router.get("/orders/health")
def orders_health():
    """Health check endpoint for the order service."""
    return health_check()

@router.get("/orders/metrics")
def get_metrics():
    """Return Prometheus-formatted metrics."""
    return generate_latest()
    
@router.get("/orders")
def get_orders(request: Request, limit: int = 20, offset: int = 0):
    """List orders with pagination."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return list_orders(limit=limit, offset=offset)
@router.post("/orders")
def post_order(request: Request, order: OrderCreate):
    """Create a new order."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return create_order(order, request_id=correlation_id)

@router.get("/orders")
def get_orders(request: Request, limit: int = 20, offset: int = 0):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return list_orders(limit=limit, offset=offset)


@router.post("/orders")
def post_order(request: Request, order: OrderCreate):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return create_order(order, request_id=correlation_id)
