import random
from locust import task, between
from locust import FastHttpUser


class NotificationUser(FastHttpUser):
    wait_time = between(3, 6)

    @task(2)
    def send_notification(self):
        payload = {
            "type": random.choice([
                "order_confirmed",
                "payment_received",
                "inventory_reserved",
                "order_shipped",
            ]),
            "order_id": random.randint(1, 1000),
        }
        with self.client.post(
            "/notifications",
            json=payload,
            catch_response=True,
            name="/notifications",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def health_check(self):
        self.client.get(
            "/health",
            name="/health",
        )