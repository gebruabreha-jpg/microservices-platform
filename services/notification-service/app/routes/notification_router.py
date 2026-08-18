import uuid
from fastapi import APIRouter, HTTPException, Request
from app.service.notification_service import health_check, get_metrics, list_notifications, send_notification
from app.schema.notification_schema import NotificationCreate

router = APIRouter()


@router.get("/health")
def health():
    return health_check()


@router.get("/metrics")
def metrics():
    return get_metrics()


@router.get("/notifications")
def get_notifications(request: Request, limit: int = 20, offset: int = 0):
    return list_notifications(limit=limit, offset=offset)


@router.post("/notifications")
def post_notification(request: Request, notification: NotificationCreate):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return send_notification(notification, request_id=correlation_id)
