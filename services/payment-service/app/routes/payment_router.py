import uuid
from fastapi import APIRouter, HTTPException, Request
from app.service.payment_service import health_check, get_metrics, list_payments, process_payment
from app.schema.payment_schema import PaymentCreate

router = APIRouter()


@router.get("/health")
def health():
    return health_check()


@router.get("/metrics")
def metrics():
    return get_metrics()


@router.get("/payments")
def get_payments(request: Request, limit: int = 20, offset: int = 0):
    return list_payments(limit=limit, offset=offset)


@router.post("/payments")
def post_payment(request: Request, payment: PaymentCreate):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return process_payment(payment, request_id=correlation_id)
