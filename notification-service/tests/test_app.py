import pytest
from starlette.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.get_json()["service"] == "notification-service"


class TestSendNotification:
    def test_notification_queued(self, client):
        response = client.post(
            "/notifications",
            json={"type": "order_confirmed", "order_id": 1},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.get_json()["status"] == "queued"