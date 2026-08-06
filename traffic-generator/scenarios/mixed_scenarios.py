import random
from locust import task, between
from locust import FastHttpUser


class MixedUser(FastHttpUser):
    wait_time = between(1, 4)

    tasks = {
        "create_order": 3,
        "list_orders": 2,
        "list_inventory": 2,
        "reserve_inventory": 1,
        "list_payments": 2,
        "process_payment": 1,
        "send_notification": 1,
        "health_check": 1,
    }

    def on_start(self):
        self.order_ids = []
        self.customer_id = random.randint(1, 100)

    @task
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

    @task
    def list_orders(self):
        self.client.get("/orders", name="/orders")

    @task
    def list_inventory(self):
        self.client.get("/inventory", name="/inventory")

    @task
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

    @task
    def list_payments(self):
        self.client.get("/payments", name="/payments")

    @task
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

    @task
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

    @task
    def health_check(self):
        self.client.get("/health", name="/health")

    @task
    def get_metrics(self):
        self.client.get("/metrics", name="/metrics")