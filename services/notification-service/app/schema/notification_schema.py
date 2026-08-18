from pydantic import BaseModel
from typing import Optional


class NotificationCreate(BaseModel):
    type: str
    order_id: int
    status: str = "queued"


class NotificationResponse(BaseModel):
    id: int
    type: str
    order_id: int
    status: str
