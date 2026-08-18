import uuid
from fastapi import APIRouter, HTTPException, Request
from app.service.order_service import health_check, get_metrics, list_orders, create_order
from app.schema.order_schema import OrderCreate

router = APIRouter()


@router.get("/health")
def health():
    return health_check()


@router.get("/metrics")
def metrics():
    return get_metrics()


@router.get("/orders")
def get_orders(request: Request, limit: int = 20, offset: int = 0):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return list_orders(limit=limit, offset=offset)


@router.post("/orders")
def post_order(request: Request, order: OrderCreate):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return create_order(order, request_id=correlation_id)
