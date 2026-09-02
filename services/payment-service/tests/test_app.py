import pytest
from starlette.testclient import TestClient

from app.main import app
from app.routes import payment_router


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["service"] == "payment-service"

    def test_ready_reports_dependencies(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.core.database.check_dependencies",
            lambda: {"postgres": True, "rabbitmq": True},
        )
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestMetrics:
    def test_metrics_returns_prometheus_text(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")


class TestProcessPayment:
    def test_payment_success(self, client, monkeypatch):
        async def fake_process(payment, request_id=None):
            return {
                "id": 1,
                "order_id": 1,
                "amount": 59.98,
                "status": "processing",
                "correlation_id": "abc-123",
            }

        monkeypatch.setattr(payment_router.payment_service, "process_payment", fake_process)
        response = client.post("/payments", json={"order_id": 1, "amount": 59.98})
        assert response.status_code == 200
        assert response.json()["status"] == "processing"


class TestListPayments:
    def test_list_payments_empty(self, client, monkeypatch):
        async def fake_list(limit=20, offset=0):
            return []

        monkeypatch.setattr(payment_router.payment_service, "list_payments", fake_list)
        response = client.get("/payments")
        assert response.status_code == 200
        assert response.json() == []
