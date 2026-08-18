from pydantic import BaseModel
from typing import Optional


class PaymentCreate(BaseModel):
    order_id: int
    amount: float
    status: str = "processing"


class PaymentResponse(BaseModel):
    id: int
    order_id: int
    amount: float
    status: str
