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
        assert response.json()["service"] == "inventory-service"


class TestReserveInventory:
    def test_reserve_success(self, client):
        with patch("app.main.get_db") as mock_db:
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = [1]
            mock_db.return_value.cursor.return_value = mock_cur
            response = client.post(
                "/inventory/reserve",
                json={"product_id": 1, "quantity": 2},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "reserved"

    def test_reserve_insufficient(self, client):
        with patch("app.main.get_db") as mock_db:
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = None
            mock_db.return_value.cursor.return_value = mock_cur
            response = client.post(
                "/inventory/reserve",
                json={"product_id": 1, "quantity": 999},
            )
        assert response.status_code == 400