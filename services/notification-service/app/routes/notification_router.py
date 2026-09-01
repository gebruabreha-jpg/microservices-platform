"""
Notification Service - API Routes
"""

from fastapi import APIRouter, Request
from app.service.notification_service import list_notifications, send_notification
from app.schema.notification_schema import NotificationCreate, NotificationResponse

router = APIRouter()


@router.get("/notifications", response_model=list[NotificationResponse])
def get_notifications(request: Request, limit: int = 20, offset: int = 0):
    """List notifications with pagination."""
    return list_notifications(limit=limit, offset=offset)


@router.post("/notifications", response_model=NotificationResponse)
def post_notification(request: Request, notification: NotificationCreate):
    """Send a new notification."""
    correlation_id = request.state.correlation_id
    return send_notification(notification, request_id=correlation_id)
