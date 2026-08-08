from fastapi import FastAPI
import pika
import json
import os
import threading

app = FastAPI()


def handle_notification(ch, method, properties, body):
    message = json.loads(body)
    print(f"Dispatching notification: {message}")


def start_consumer():
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
                port=5672,
                credentials=pika.PlainCredentials(
                    os.getenv("RABBITMQ_USER", "admin"),
                    os.getenv("RABBITMQ_PASS", "secret"),
                ),
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue="notifications", durable=True)
        channel.basic_consume(queue="notifications", on_message_callback=handle_notification, auto_ack=True)
        channel.start_consuming()
    except Exception:
        pass


consumer_thread = threading.Thread(target=start_consumer, daemon=True)
consumer_thread.start()


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service"}


@app.get("/metrics")
def metrics():
    return {"service": "notification-service"}


@app.post("/notifications")
def send_notification(notification: dict):
    return {"id": 1, "status": "queued", "type": notification.get("type")}
