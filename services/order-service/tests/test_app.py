import pytest
from starlette.testclient import TestClient

from app.main import app
from app.routes import order_router


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["service"] == "order-service"

    def test_ready(self, client):
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True


class TestMetrics:
    def test_metrics_returns_prometheus_text(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")


class TestCreateOrder:
    def test_create_order_success(self, client, monkeypatch):
        async def fake_create(order, request_id=None):
            return {
                "id": 1,
                "customer_id": 1,
                "product_id": 1,
                "quantity": 2,
                "amount": 59.98,
                "status": "created",
                "correlation_id": "abc-123",
            }

        monkeypatch.setattr(order_router.order_service, "create_order", fake_create)
        response = client.post(
            "/orders",
            json={"customer_id": 1, "product_id": 1, "quantity": 2, "amount": 59.98},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["status"] == "created"


class TestListOrders:
    def test_list_orders_empty(self, client, monkeypatch):
        async def fake_list(limit=20, offset=0):
            return []

        monkeypatch.setattr(order_router.order_service, "list_orders", fake_list)
        response = client.get("/orders")
        assert response.status_code == 200
        assert response.json() == []


class TestGetOrder:
    def test_get_order_found(self, client, monkeypatch):
        async def fake_get(order_id):
            return {
                "id": order_id,
                "customer_id": 1,
                "product_id": 1,
                "quantity": 2,
                "amount": 59.98,
                "status": "created",
            }

        monkeypatch.setattr(order_router.order_service, "get_order", fake_get)
        response = client.get("/orders/7")
        assert response.status_code == 200
        assert response.json()["id"] == 7

    def test_get_order_missing(self, client, monkeypatch):
        async def fake_get(order_id):
            return None

        monkeypatch.setattr(order_router.order_service, "get_order", fake_get)
        response = client.get("/orders/999")
        assert response.status_code == 404
