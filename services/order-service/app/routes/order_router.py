from fastapi import APIRouter, HTTPException
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
def get_orders():
    return list_orders()


@router.post("/orders")
def post_order(order: OrderCreate):
    return create_order(order)
