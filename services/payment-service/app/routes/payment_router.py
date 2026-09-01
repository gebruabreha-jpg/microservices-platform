"""
Payment Service - API Routes.

METRICS ENDPOINT:
  Returns Prometheus text format for direct scraping.
  Primary metrics path is OTLP -> OTel Collector -> Prometheus.
"""

from fastapi import APIRouter, Request
from app.service.payment_service import list_payments, process_payment
from app.schema.payment_schema import PaymentCreate, PaymentResponse

router = APIRouter()


@router.get("/payments", response_model=list[PaymentResponse])
def get_payments(request: Request, limit: int = 20, offset: int = 0):
    return list_payments(limit=limit, offset=offset)


@router.post("/payments", response_model=PaymentResponse)
def post_payment(request: Request, payment: PaymentCreate):
    correlation_id = request.state.correlation_id
    return process_payment(payment, request_id=correlation_id)
