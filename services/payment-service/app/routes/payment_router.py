from fastapi import APIRouter, HTTPException
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
def get_payments():
    return list_payments()


@router.post("/payments")
def post_payment(payment: PaymentCreate):
    return process_payment(payment)
