# notification-service

Receives notification jobs from RabbitMQ and dispatches notifications.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| POST | `/notifications` | Queue a notification |