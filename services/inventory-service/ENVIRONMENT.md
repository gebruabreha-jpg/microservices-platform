# Inventory Service — Environment Details

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Service metrics |
| GET | `/inventory` | List all inventory items |
| POST | `/inventory/reserve` | Reserve inventory for a product |

### Request/Response Examples

**Reserve Inventory**
```json
POST /inventory/reserve
{
  "product_id": 1,
  "quantity": 2
}
```

```json
200 OK
{
  "id": 1,
  "status": "reserved"
}
```

```json
400 Bad Request
{
  "detail": "Insufficient inventory"
}
```

**List Inventory**
```json
GET /inventory
[
  {
    "id": 1,
    "product_id": 1,
    "quantity": 100,
    "reserved": 20
  }
]
```

## Database Schema

**Table: inventory**

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PRIMARY KEY | Auto-incrementing item ID |
| product_id | INTEGER | Product identifier |
| quantity | INTEGER | Total available quantity |
| reserved | INTEGER | Quantity currently reserved |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_HOST | postgres | PostgreSQL host |
| POSTGRES_PORT | 5432 | PostgreSQL port |
| POSTGRES_DB | appdb | Database name |
| POSTGRES_USER | admin | Database user |
| POSTGRES_PASSWORD | secret | Database password |

## Dependencies

- PostgreSQL — inventory data persistence
- shared-python-lib — InventoryItem model, config, logger, telemetry