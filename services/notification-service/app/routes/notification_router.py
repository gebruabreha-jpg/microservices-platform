"""
Notification Service - API Routes

Uses DI container to get service instances.
"""

from fastapi import APIRouter, Depends, Request
from app.container import get_container
from app.schema.notification_schema import NotificationCreate, NotificationResponse
from app.service.notification_service import NotificationService

router = APIRouter()


def get_notification_service() -> NotificationService:
    """FastAPI dependency provider - returns the process-wide NotificationService
    singleton so tests can override it via app.dependency_overrides."""
    return get_container().get_notification_service()


# Module-level handle kept for existing tests that monkeypatch it directly;
# it is the same singleton instance get_notification_service() returns.
notification_service = get_notification_service()


@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notifications(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    service: NotificationService = Depends(get_notification_service),
):
    """List notifications with pagination."""
    return await service.list_notifications(limit=limit, offset=offset)


@router.post("/notifications", response_model=NotificationResponse)
async def post_notification(
    request: Request,
    notification: NotificationCreate,
    service: NotificationService = Depends(get_notification_service),
):
    """Send a new notification."""
    correlation_id = request.state.correlation_id
    return await service.send_notification(notification, request_id=correlation_id)
