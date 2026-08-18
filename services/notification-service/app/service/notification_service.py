import json
from app.repository.notification_repository import create_notification, get_all_notifications
from app.core.database import get_rabbitmq_connection


def health_check():
    return {"status": "ok", "service": "notification-service"}


def get_metrics():
    return {"service": "notification-service"}


def list_notifications():
    rows = get_all_notifications()
    return [
        {
            "id": r[0],
            "type": r[1],
            "order_id": r[2],
            "status": r[3],
        }
        for r in rows
    ]


def send_notification(notification_data):
    notification_id = create_notification(notification_data)
    return {"id": notification_id, "status": "queued"}


def handle_notification(ch, method, properties, body):
    message = json.loads(body)
    from app.schema.notification_schema import NotificationCreate
    notification = NotificationCreate(
        type=message.get("type"),
        order_id=message.get("order_id"),
        status="queued",
    )
    send_notification(notification)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consumer():
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            channel.queue_declare(queue="notifications", durable=True)
            channel.basic_consume(queue="notifications", on_message_callback=handle_notification, auto_ack=False)
            channel.start_consuming()
        except Exception:
            pass
