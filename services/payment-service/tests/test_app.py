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
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["service"] == "payment-service"


class TestMetrics:
    def test_metrics_returns_json(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.json()["service"] == "payment-service"


class TestProcessPayment:
    def test_payment_success(self, client):
        with patch("app.service.payment_service.create_payment") as mock_create, \
             patch("app.service.payment_service.queue_rabbitmq_job"):
            mock_create.return_value = 1
            response = client.post(
                "/payments",
                json={"order_id": 1, "amount": 59.98},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "processing"


class TestListPayments:
    def test_list_payments_empty(self, client):
        with patch("app.routes.payment_router.list_payments") as mock_list:
            mock_list.return_value = []
            response = client.get("/payments")
        assert response.status_code == 200
        assert response.json() == []
