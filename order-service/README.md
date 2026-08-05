# order-service

Manages orders: create, list, and cache results in Redis. Publishes events to Kafka.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| GET | `/orders` | List all orders |
| POST | `/orders` | Create a new order |

## Events Published

- `orders` — OrderCreated event to Kafka