from fastapi import APIRouter, FastAPI, WebSocket
from app.service import creat_order, get_order, get_metrics, health_check
router=APIRouter()

@router.post("/orders")
@router.get("/orders")
@router.get("/metrics")
@router.get("/health")