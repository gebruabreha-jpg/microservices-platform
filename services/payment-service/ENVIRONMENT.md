# Payment Service — Environment Details

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Service metrics |
| GET | `/payments` | List all payments |
| POST | `/payments` | Process a new payment |

### Request/Response Examples

**Process Payment**
```json
POST /payments
{
  "order_id": 1,
  "amount": 59.98
}
```

```json
201 Created
{
  "id": 1,
  "status": "processing"
}
```

**List Payments**
```json
GET /payments
[
  {
    "id": 1,
    "order_id": 1,
    "amount": 59.98,
    "status": "processing"
  }
]
```

## Database Schema

**Table: payments**

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PRIMARY KEY | Auto-incrementing payment ID |
| order_id | INTEGER | Associated order ID |
| amount | DECIMAL(10,2) | Payment amount |
| status | VARCHAR(50) DEFAULT 'processing' | Payment status |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_HOST | postgres | PostgreSQL host |
| POSTGRES_PORT | 5432 | PostgreSQL port |
| POSTGRES_DB | appdb | Database name |
| POSTGRES_USER | admin | Database user |
| POSTGRES_PASSWORD | secret | Database password |
| RABBITMQ_HOST | rabbitmq | RabbitMQ host |
| RABBITMQ_USER | admin | RabbitMQ user |
| RABBITMQ_PASS | secret | RabbitMQ password |

## Message Queue

Publishes payment events to RabbitMQ queue `notifications`:
```json
{
  "type": "payment_received",
  "payment_id": 1,
  "order_id": 1
}
```

## Dependencies

- PostgreSQL — payment persistence
- RabbitMQ — async notification dispatch
- shared-python-lib — Payment model, config, logger, telemetry