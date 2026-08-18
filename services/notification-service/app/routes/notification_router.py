from fastapi import APIRouter, HTTPException
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
def get_notifications():
    return list_notifications()


@router.post("/notifications")
def post_notification(notification: NotificationCreate):
    return send_notification(notification)
