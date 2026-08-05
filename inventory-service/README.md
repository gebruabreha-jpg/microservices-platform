# inventory-service

Manages product inventory and reservation.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| GET | `/inventory` | List inventory |
| POST | `/inventory/reserve` | Reserve inventory for a product |