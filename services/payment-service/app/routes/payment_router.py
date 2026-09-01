"""
Payment Service - API Routes.

Uses DI container to get service instances.
"""

from fastapi import APIRouter, Request
from app.container import Container
from app.schema.payment_schema import PaymentCreate, PaymentResponse

router = APIRouter()

# Get service from DI container
container = Container()
payment_service = container.get_payment_service()


@router.get("/payments", response_model=list[PaymentResponse])
async def get_payments(request: Request, limit: int = 20, offset: int = 0):
    """List payments with pagination."""
    return await payment_service.list_payments(limit=limit, offset=offset)


@router.post("/payments", response_model=PaymentResponse)
async def post_payment(request: Request, payment: PaymentCreate):
    """Process a new payment."""
    correlation_id = request.state.correlation_id
    return await payment_service.process_payment(payment, request_id=correlation_id)
