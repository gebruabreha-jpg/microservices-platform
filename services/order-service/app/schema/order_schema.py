from pydantic import BaseModel
from typing import Optional


class OrderCreate(BaseModel):
    customer_id: int
    product_id: int
    quantity: int
    amount: float
    status: str = "created"


class OrderResponse(BaseModel):
    id: int
    customer_id: int
    product_id: int
    quantity: int
    amount: float
    status: str
