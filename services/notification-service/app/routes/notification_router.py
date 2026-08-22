"""
Notification Service - API Routes

METRICS ENDPOINT:
  Returns Prometheus text format for direct scraping.
  Primary metrics path is OTLP -> OTel Collector -> Prometheus.
"""

import uuid
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from app.service.notification_service import health_check, list_notifications, send_notification
from app.schema.notification_schema import NotificationCreate

router = APIRouter()


@router.get("/health")
def health():
    return health_check()


# =============================================================================
# METRICS: Prometheus text format endpoint
# =============================================================================
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    @router.get("/metrics")
    async def metrics():
        """Return Prometheus-formatted metrics."""
        return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
except ImportError:
    @router.get("/metrics")
    def metrics_fallback():
        return {"service": "notification-service", "metrics": "prometheus_client not installed"}


@router.get("/notifications")
def get_notifications(request: Request, limit: int = 20, offset: int = 0):
    return list_notifications(limit=limit, offset=offset)


@router.post("/notifications")
def post_notification(request: Request, notification: NotificationCreate):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    return send_notification(notification, request_id=correlation_id)
