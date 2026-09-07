"""
Payment Service - API Routes.

Uses DI container to get service instances.
"""

from fastapi import APIRouter, Depends, Request
from app.container import get_container
from app.schema.payment_schema import PaymentCreate, PaymentResponse
from app.service.payment_service import PaymentService

router = APIRouter()


def get_payment_service() -> PaymentService:
    """FastAPI dependency provider - returns the process-wide PaymentService
    singleton so tests can override it via app.dependency_overrides."""
    return get_container().get_payment_service()


# Module-level handle kept for existing tests that monkeypatch it directly;
# it is the same singleton instance get_payment_service() returns.
payment_service = get_payment_service()


@router.get("/payments", response_model=list[PaymentResponse])
async def get_payments(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    service: PaymentService = Depends(get_payment_service),
):
    """List payments with pagination."""
    return await service.list_payments(limit=limit, offset=offset)


@router.post("/payments", response_model=PaymentResponse)
async def post_payment(
    request: Request, payment: PaymentCreate, service: PaymentService = Depends(get_payment_service)
):
    """Process a new payment."""
    correlation_id = request.state.correlation_id
    return await service.process_payment(payment, request_id=correlation_id)
