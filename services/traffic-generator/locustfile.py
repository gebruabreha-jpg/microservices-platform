import random
import time
from locust import events
from locust.contrib.fasthttp import FastHttpUser


API_BASE = "http://nginx"


class OrderUser(FastHttpUser):
    wait_time = between(1, 3)
    host = API_BASE

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

    def on_stop(self):
        pass


class InventoryUser(FastHttpUser):
    wait_time = between(2, 5)
    host = API_BASE

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


class PaymentUser(FastHttpUser):
    wait_time = between(2, 4)
    host = API_BASE

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


class NotificationUser(FastHttpUser):
    wait_time = between(3, 6)
    host = API_BASE

    @task(2)
    def send_notification(self):
        payload = {
            "type": random.choice(["order_confirmed", "payment_received", "inventory_reserved", "order_shipped"]),
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


class MixedUser(FastHttpUser):
    wait_time = between(1, 4)
    host = API_BASE

    tasks = {
        OrderUser.create_order: 3,
        OrderUser.list_orders: 2,
        InventoryUser.list_inventory: 2,
        InventoryUser.reserve_inventory: 1,
        PaymentUser.list_payments: 2,
        PaymentUser.process_payment: 1,
        NotificationUser.send_notification: 1,
        OrderUser.health_check: 1,
    }

    @task
    def get_metrics(self):
        self.client.get(
            "/metrics",
            name="/metrics",
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    environment.runner.order_ids = []


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    pass


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    pass