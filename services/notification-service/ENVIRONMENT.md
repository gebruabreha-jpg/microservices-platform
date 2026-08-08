# Notification Service — Environment Details

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Service metrics |
| POST | `/notifications` | Queue a notification request |

### Request/Response Examples

**Send Notification**
```json
POST /notifications
{
  "type": "order_confirmed",
  "order_id": 1
}
```

```json
200 OK
{
  "id": 1,
  "status": "queued",
  "type": "order_confirmed"
}
```

**Notification Types**
- `order_confirmed` — Order has been confirmed
- `payment_received` — Payment has been processed
- `inventory_reserved` — Inventory has been reserved
- `order_shipped` — Order has been shipped

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| RABBITMQ_HOST | rabbitmq | RabbitMQ host |
| RABBITMQ_USER | admin | RabbitMQ user |
| RABBITMQ_PASS | secret | RabbitMQ password |

## Message Queue

Consumes from RabbitMQ queue `notifications` (durable queue). Messages are dispatched in a background daemon thread.

## Dependencies

- RabbitMQ — message consumer for async notifications
- shared-python-lib — config, logger, telemetry