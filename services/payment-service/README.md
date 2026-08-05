# payment-service

Processes payments and queues notification jobs via RabbitMQ.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| GET | `/payments` | List payments |
| POST | `/payments` | Process a payment |