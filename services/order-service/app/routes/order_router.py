"""
Order Service - API Routes
"""

from fastapi import APIRouter, Request
from app.service.order_service import list_orders, create_order
from app.schema.order_schema import OrderCreate, OrderResponse

router = APIRouter()


@router.post("/orders", response_model=OrderResponse)
async def post_order(request: Request, order: OrderCreate):
    """Create a new order."""
    correlation_id = request.state.correlation_id
    return await create_order(order, request_id=correlation_id)



@router.get("/orders", response_model=list[OrderResponse])
async def get_orders(request: Request, limit: int = 20, offset: int = 0):
    """List orders with pagination."""
    return await list_orders(limit=limit, offset=offset)
