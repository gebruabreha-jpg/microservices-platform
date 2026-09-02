import pytest
from starlette.testclient import TestClient

from app.main import app
from app.routes import notification_router


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["service"] == "notification-service"

    def test_ready(self, client):
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True


class TestMetrics:
    def test_metrics_returns_prometheus_text(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")


class TestSendNotification:
    def test_send_notification_success(self, client, monkeypatch):
        async def fake_send(notification, request_id=None):
            return {
                "id": 1,
                "type": "order_confirmed",
                "order_id": 1,
                "status": "queued",
                "correlation_id": "abc-123",
            }

        monkeypatch.setattr(notification_router.notification_service, "send_notification", fake_send)
        response = client.post("/notifications", json={"type": "order_confirmed", "order_id": 1})
        assert response.status_code == 200
        assert response.json()["status"] == "queued"


class TestListNotifications:
    def test_list_notifications_empty(self, client, monkeypatch):
        async def fake_list(limit=20, offset=0):
            return []

        monkeypatch.setattr(notification_router.notification_service, "list_notifications", fake_list)
        response = client.get("/notifications")
        assert response.status_code == 200
        assert response.json() == []
