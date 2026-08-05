import random
from locust import task, between
from locust.contrib.fasthttp import FastHttpUser


class InventoryUser(FastHttpUser):
    wait_time = between(2, 5)

    @task(3)
    def list_inventory(self):
        self.client.get(
            "/inventory",
            name="/inventory",
        )

    @task(2)
    def reserve_inventory(self):
        payload = {
            "product_id": random.randint(1, 50),
            "quantity": random.randint(1, 5),
        }
        with self.client.post(
            "/inventory/reserve",
            json=payload,
            catch_response=True,
            name="/inventory/reserve",
        ) as response:
            if response.status_code in (200, 400):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def health_check(self):
        self.client.get(
            "/health",
            name="/health",
        )