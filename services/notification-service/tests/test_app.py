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
        assert response.json()["service"] == "notification-service"


class TestMetrics:
    def test_metrics_returns_json(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.json()["service"] == "notification-service"
