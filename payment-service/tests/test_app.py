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
        assert response.get_json()["service"] == "payment-service"


class TestProcessPayment:
    def test_payment_success(self, client):
        with patch("app.main.get_db") as mock_db, patch("app.main.queue_rabbitmq_job"):
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = [1]
            mock_db.return_value.cursor.return_value = mock_cur
            response = client.post(
                "/payments",
                json={"order_id": 1, "amount": 59.98},
                content_type="application/json",
            )
        assert response.status_code == 200
        assert response.get_json()["status"] == "processing"