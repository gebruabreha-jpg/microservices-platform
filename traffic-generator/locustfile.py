import random
import time
import csv
import os
from locust import task, between
from locust import FastHttpUser

# Best practice: configure host via CLI flag (--host) instead of hardcoding, 
# but keeping this as a fallback.
API_BASE = "http://nginx"



class OrderUser(FastHttpUser):
    wait_time = between(1, 3)
    host = API_BASE

    def on_start(self):
        self.customer_id = random.randint(1, 100)
        self.created_order_ids = [] # Used to make realistic downstream requests

    @task(3)
    def create_order(self):
        payload = {
            "customer_id": self.customer_id,
            "product_id": random.randint(1, 50),
            "quantity": random.randint(1, 10),
            "amount": round(random.uniform(5.0, 200.0), 2),
        }
         # self.client.rest automatically catches non-2xx status codes as failures instade of:- with self.client.post("/orders", json=payload, name="/orders") as response:
        with self.client.rest("POST", "/orders", json=payload, name="/orders") as response:
            if response.status_code == 200 and "id" in response.js:
                self.created_order_ids.append(response.js["id"])


    @task(2)
    def list_orders(self):
        # Realistic testing: 50% chance to view a specific order they made
        if self.created_order_ids and random.choice([True, False]):
            order_id = random.choice(self.created_order_ids)
            self.client.get(f"/orders/{order_id}", name="/orders/[id]")
        else:
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

    @task(3)
    def list_payments(self):
        self.client.get("/payments", name="/payments")

    @task(2)
    def process_payment(self):
        payload = {
            "order_id": random.randint(1, 1000),
            "amount": round(random.uniform(5.0, 500.0), 2),
        }
        # Simplified using rest()
        self.client.rest("POST", "/payments", json=payload, name="/payments")

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
        self.client.rest("POST", "/notifications", json=payload, name="/notifications")

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
        self.client.rest("POST", "/orders", json=payload, name="/orders")

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
        self.client.rest("POST", "/payments", json=payload, name="/payments")

    @task(1)
    def send_notification(self):
        payload = {
            "type": random.choice(["order_confirmed", "payment_received", "order_shipped"]),
            "order_id": random.randint(1, 1000),
        }
        self.client.rest("POST", "/notifications", json=payload, name="/notifications")

    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task
    def get_metrics(self):
        self.client.get("/metrics", name="/metrics")