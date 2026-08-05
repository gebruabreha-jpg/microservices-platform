from pydantic import BaseModel
from typing import Optional


class Order(BaseModel):
    id: Optional[int] = None
    customer_id: int
    product_id: int
    quantity: int
    amount: float
    status: str = "created"


class Payment(BaseModel):
    id: Optional[int] = None
    order_id: int
    amount: float
    status: str = "processing"


class InventoryItem(BaseModel):
    id: Optional[int] = None
    product_id: int
    quantity: int
    reserved: int = 0