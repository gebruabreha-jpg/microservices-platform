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
        assert response.json()["service"] == "order-service"


class TestMetrics:
    def test_metrics_returns_json(self, client):
        with patch("app.routes.order_router.get_metrics") as mock_metrics:
            mock_metrics.return_value = {"orders_requests_total": 5}
            response = client.get("/metrics")
        assert response.status_code == 200
        assert "orders_requests_total" in response.json()


class TestCreateOrder:
    def test_create_order_success(self, client):
        with patch("app.routes.order_router.create_order") as mock_create:
            mock_create.return_value = {"id": 1, "status": "created"}
            response = client.post(
                "/orders",
                json={"customer_id": 1, "product_id": 1, "quantity": 2, "amount": 59.98},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["status"] == "created"


class TestListOrders:
    def test_list_orders_empty(self, client):
        with patch("app.routes.order_router.list_orders") as mock_list:
            mock_list.return_value = []
            response = client.get("/orders")
        assert response.status_code == 200
        assert response.json() == []
