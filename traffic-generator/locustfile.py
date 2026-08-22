import random
import time
import csv
import os
from locust import events, task, between
from locust import FastHttpUser


API_BASE = "http://nginx"

RESULTS_DIR = "/results"
os.makedirs(RESULTS_DIR, exist_ok=True)


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
        self.client.get("/orders", name="/orders")

    @task(1)
    def get_metrics(self):
        self.client.get("/metrics", name="/metrics")

    @task(1)
    def health_check(self):
        self.client.get("/health/order", name="/health/order")


class PaymentUser(FastHttpUser):
    wait_time = between(2, 4)
    host = API_BASE

    def on_start(self):
        self.order_ids = []

    @task(3)
    def list_payments(self):
        self.client.get("/payments", name="/payments")

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
        self.client.get("/health/payment", name="/health/payment")


class NotificationUser(FastHttpUser):
    wait_time = between(3, 6)
    host = API_BASE

    @task(2)
    def send_notification(self):
        payload = {
            "type": random.choice(["order_confirmed", "payment_received", "order_shipped"]),
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
        self.client.get("/health/notification", name="/health/notification")


class MixedUser(FastHttpUser):
    wait_time = between(1, 4)
    host = API_BASE

    @task(3)
    def create_order(self):
        payload = {
            "customer_id": random.randint(1, 100),
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
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def list_orders(self):
        self.client.get("/orders", name="/orders")

    @task(2)
    def list_payments(self):
        self.client.get("/payments", name="/payments")

    @task(1)
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
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def send_notification(self):
        payload = {
            "type": random.choice(["order_confirmed", "payment_received", "order_shipped"]),
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
        self.client.get("/health", name="/health")

    @task
    def get_metrics(self):
        self.client.get("/metrics", name="/metrics")


metrics_data = {
    "requests": [],
    "failures": [],
    "start_time": None,
    "end_time": None,
}


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    metrics_data["start_time"] = time.time()
    metrics_data["requests"] = []
    metrics_data["failures"] = []
    print(f"Test started at {metrics_data['start_time']}")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    metrics_data["requests"].append({
        "timestamp": time.time(),
        "request_type": request_type,
        "name": name,
        "response_time": response_time,
        "response_length": response_length,
        "exception": str(exception) if exception else None,
    })
    if exception:
        metrics_data["failures"].append({
            "timestamp": time.time(),
            "request_type": request_type,
            "name": name,
            "exception": str(exception),
        })


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    metrics_data["end_time"] = time.time()
    duration = metrics_data["end_time"] - metrics_data["start_time"]
    total_requests = len(metrics_data["requests"])
    total_failures = len(metrics_data["failures"])
    success_rate = ((total_requests - total_failures) / total_requests * 100) if total_requests > 0 else 0
    avg_response_time = sum(r["response_time"] for r in metrics_data["requests"]) / total_requests if total_requests > 0 else 0

    summary = {
        "duration_seconds": round(duration, 2),
        "total_requests": total_requests,
        "total_failures": total_failures,
        "success_rate_percent": round(success_rate, 2),
        "avg_response_time_ms": round(avg_response_time, 2),
    }

    csv_path = os.path.join(RESULTS_DIR, "locust_summary.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary.keys())
        writer.writeheader()
        writer.writerow(summary)

    requests_csv = os.path.join(RESULTS_DIR, "locust_requests.csv")
    with open(requests_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "request_type", "name", "response_time", "response_length", "exception"])
        writer.writeheader()
        writer.writerows(metrics_data["requests"])

    failures_csv = os.path.join(RESULTS_DIR, "locust_failures.csv")
    with open(failures_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "request_type", "name", "exception"])
        writer.writeheader()
        writer.writerows(metrics_data["failures"])

    print(f"Test completed. Results saved to {RESULTS_DIR}")
    print(f"Summary: {summary}")
