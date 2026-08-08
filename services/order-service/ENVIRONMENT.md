# Order Service — Environment Details

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Service metrics |
| GET | `/orders` | List all orders |
| POST | `/orders` | Create a new order |

### Request/Response Examples

**Create Order**
```json
POST /orders
{
  "customer_id": 1,
  "product_id": 1,
  "quantity": 2,
  "amount": 59.98
}
```

```json
201 Created
{
  "id": 1,
  "status": "created"
}
```

**List Orders**
```json
GET /orders
[
  {
    "id": 1,
    "customer_id": 1,
    "product_id": 1,
    "quantity": 2,
    "amount": 59.98,
    "status": "created"
  }
]
```

## Database Schema

**Table: orders**

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PRIMARY KEY | Auto-incrementing order ID |
| customer_id | INTEGER | Customer identifier |
| product_id | INTEGER | Product identifier |
| quantity | INTEGER | Number of items ordered |
| amount | DECIMAL(10,2) | Total order amount |
| status | VARCHAR(50) DEFAULT 'created' | Order status |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_HOST | postgres | PostgreSQL host |
| POSTGRES_PORT | 5432 | PostgreSQL port |
| POSTGRES_DB | appdb | Database name |
| POSTGRES_USER | admin | Database user |
| POSTGRES_PASSWORD | secret | Database password |
| REDIS_HOST | redis | Redis host |
| REDIS_PORT | 6379 | Redis port |
| KAFKA_REST_URL | http://kafka-rest:8082 | Kafka REST proxy URL |

## Dependencies

- PostgreSQL — order persistence
- Redis — caching and metrics counter
- Kafka — event streaming (order.created events)
- shared-python-lib — Order model, config, logger, telemetry