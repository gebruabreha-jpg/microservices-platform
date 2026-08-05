import random
from locust import task, between
from locust.contrib.fasthttp import FastHttpUser


class PaymentUser(FastHttpUser):
    wait_time = between(2, 4)

    def on_start(self):
        self.order_ids = []

    @task(3)
    def list_payments(self):
        self.client.get(
            "/payments",
            name="/payments",
        )

    @task(2)
    def process_payment(self):
        payload = {
            "order_id": random.randint(1, 1000),
            "amount": round(random.uniform(5.0, 500.0), 2),
        }
        with self.client.post(
            "/payments",
            json=payload,
            catch_response=True,
            name="/payments",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "id" in data:
                    self.order_ids.append(data["id"])
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def health_check(self):
        self.client.get(
            "/health",
            name="/health",
        )