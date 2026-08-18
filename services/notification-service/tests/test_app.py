import pytest
from starlette.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_check(self, client):
        with patch("app.service.notification_service.check_dependencies") as mock_deps:
            mock_deps.return_value = {"postgres": True, "rabbitmq": True}
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["service"] == "notification-service"


class TestMetrics:
    def test_metrics_returns_json(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.json()["service"] == "notification-service"


class TestSendNotification:
    def test_send_notification_success(self, client):
        with patch("app.routes.notification_router.send_notification") as mock_send:
            mock_send.return_value = {"id": 1, "status": "queued", "correlation_id": "abc-123"}
            response = client.post(
                "/notifications",
                json={"type": "order_confirmed", "order_id": 1},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "queued"


class TestListNotifications:
    def test_list_notifications_empty(self, client):
        with patch("app.routes.notification_router.list_notifications") as mock_list:
            mock_list.return_value = []
            response = client.get("/notifications")
        assert response.status_code == 200
        assert response.json() == []
