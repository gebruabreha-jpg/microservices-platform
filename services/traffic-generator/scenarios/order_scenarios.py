import random
from locust import task, between
from locust.contrib.fasthttp import FastHttpUser


class OrderUser(FastHttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.order_ids = []
        self.customer_id = random.randint(1, 100)

    @task(3)
    def create_order(self):
        payload = {
            "customer_id": self.customer_id,
            "product_id": random.randint(1, 50),
            "quantity": random.randint(1, 10),
            "amount": round(random.uniform(5.0, 200.0), 2),
        }
        with self.client.post(
            "/orders",
            json=payload,
            catch_response=True,
            name="/orders",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "id" in data:
                    self.order_ids.append(data["id"])
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def list_orders(self):
        self.client.get(
            "/orders",
            name="/orders",
        )

    @task(1)
    def get_metrics(self):
        self.client.get(
            "/metrics",
            name="/metrics",
        )

    @task(1)
    def health_check(self):
        self.client.get(
            "/health",
            name="/health",
        )