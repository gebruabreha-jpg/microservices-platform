"""
Order Service - API Routes

Uses DI container to get service instances.
"""

from fastapi import APIRouter, Request
from app.container import get_container
from app.schema.order_schema import OrderCreate, OrderResponse

router = APIRouter()

# Get service from the process-wide DI container
order_service = get_container().get_order_service()


@router.post("/orders", response_model=OrderResponse)
async def post_order(request: Request, order: OrderCreate):
    """Create a new order."""
    correlation_id = request.state.correlation_id
    return await order_service.create_order(order, request_id=correlation_id)


@router.get("/orders", response_model=list[OrderResponse])
async def get_orders(request: Request, limit: int = 20, offset: int = 0):
    """List orders with pagination."""
    return await order_service.list_orders(limit=limit, offset=offset)
