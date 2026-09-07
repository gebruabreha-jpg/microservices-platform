"""
Order Service - API Routes

Uses DI container to get service instances.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.container import get_container
from app.schema.order_schema import OrderCreate, OrderResponse
from app.service.order_service import OrderService

router = APIRouter()


def get_order_service() -> OrderService:
    """FastAPI dependency provider - returns the process-wide OrderService
    singleton so tests can override it via app.dependency_overrides."""
    return get_container().get_order_service()


# Module-level handle kept for existing tests that monkeypatch it directly;
# it is the same singleton instance get_order_service() returns.
order_service = get_order_service()


@router.post("/orders", response_model=OrderResponse)
async def post_order(
    request: Request, order: OrderCreate, service: OrderService = Depends(get_order_service)
):
    """Create a new order."""
    correlation_id = request.state.correlation_id
    return await service.create_order(order, request_id=correlation_id)


@router.get("/orders", response_model=list[OrderResponse])
async def get_orders(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    service: OrderService = Depends(get_order_service),
):
    """List orders with pagination."""
    return await service.list_orders(limit=limit, offset=offset)


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    request: Request, order_id: int, service: OrderService = Depends(get_order_service)
):
    """Fetch a single order by id."""
    order = await service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order
