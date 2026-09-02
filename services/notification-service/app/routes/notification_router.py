"""
Notification Service - API Routes

Uses DI container to get service instances.
"""

from fastapi import APIRouter, Request
from app.container import get_container
from app.schema.notification_schema import NotificationCreate, NotificationResponse

router = APIRouter()

# Get service from the process-wide DI container
notification_service = get_container().get_notification_service()


@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notifications(request: Request, limit: int = 20, offset: int = 0):
    """List notifications with pagination."""
    return await notification_service.list_notifications(limit=limit, offset=offset)


@router.post("/notifications", response_model=NotificationResponse)
async def post_notification(request: Request, notification: NotificationCreate):
    """Send a new notification."""
    correlation_id = request.state.correlation_id
    return await notification_service.send_notification(notification, request_id=correlation_id)
