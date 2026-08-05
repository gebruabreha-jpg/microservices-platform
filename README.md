# Order Management System

A distributed order management system demonstrating platform and distributed systems patterns.

## Architecture

```
Client
  │
  ▼
NGINX (API Gateway)
  │
  ├── Order Service      → PostgreSQL + Redis + Kafka
  ├── Inventory Service  → PostgreSQL + Kafka
  ├── Payment Service    → PostgreSQL + RabbitMQ
  └── Notification Service → RabbitMQ
```

## Repositories

| Repository | Description |
|-----------|-------------|
| `system-design-infra/` | Shared infrastructure (PostgreSQL, Redis, NGINX, Prometheus, Grafana) |
| `order-service/` | Order management (create, list, cache) |
| `inventory-service/` | Inventory reservation |
| `payment-service/` | Payment processing |
| `notification-service/` | Notification dispatch |
| `shared-python-lib/` | Shared utilities across services |

## Quick start

### Infrastructure

```bash
cd system-design-infra
docker compose up -d
```

### Order Service

```bash
cd order-service
docker compose up -d
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Cache |
| NGINX | 80 | API Gateway |
| Prometheus | 9090 | Metrics |
| Grafana | 3000 | Dashboard |

## Concepts demonstrated

- Docker & Docker Compose
- Reverse proxy (NGINX)
- Health checks
- Metrics (Prometheus)
- Caching (Redis)
- Event streaming (Kafka)
- Message queues (RabbitMQ)
- Distributed tracing (OpenTelemetry)
- Service discovery
- Circuit breaker
- Retry logic
- Idempotency
- CQRS
- Saga pattern
- Outbox pattern