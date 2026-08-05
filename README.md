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

## API Testing vs Load Testing

This project uses different tools for different stages of development and platform validation. Each tool has a specific purpose.

### Tool Comparison

| Tool | Purpose | When to Use |
|------|---------|-------------|
| Postman | Develop and manually test APIs | During development |
| Locust | Simulate thousands of concurrent users | Load and scalability testing |
| k6 | Load, stress, and performance testing | CI/CD and performance regression testing |
| JMeter | Enterprise performance testing | Large enterprise environments |

### Postman

Postman is used to verify that an API behaves correctly.

Typical tasks include:

- Testing API endpoints
- Verifying request and response payloads
- Checking authentication
- Validating status codes
- Debugging API behavior

Example:

```
POST /orders

Expected response:

200 OK
```

Postman answers questions like:

- Does the API work?
- Is the response correct?
- Is authentication configured properly?
- Are validation errors handled correctly?

### Why Postman Is Not Enough

Postman is not designed to simulate production traffic.

It cannot realistically test scenarios such as:

- 500 concurrent users placing orders
- Kubernetes Horizontal Pod Autoscaling (HPA)
- Kafka message throughput
- Redis cache hit ratio
- PostgreSQL connection pool exhaustion
- RabbitMQ queue growth
- Prometheus metrics under sustained load

These require continuous, concurrent traffic over time.

### Locust

Locust is the primary traffic generator for this project.

It simulates realistic user behavior by continuously generating requests.

Example user actions:

- Create an order
- View an order
- Cancel an order
- Check inventory

Locust helps validate:

- Load balancing
- Kubernetes autoscaling
- Redis caching
- Kafka producers and consumers
- RabbitMQ workers
- Database performance
- API Gateway throughput
- Circuit breakers
- Retry behavior
- Distributed tracing

Example scenario:

```
500 Virtual Users

      │
      ▼
Create Orders
      │
      ▼
API Gateway
      │
      ▼
Order Service
      │
      ▼
Kafka
      │
      ▼
Inventory Service
      │
      ▼
Payment Service
      │
      ▼
Notification Service
```

### k6 (Optional)

k6 is intended for automated performance testing.

Typical use cases include:

- Smoke tests
- Load tests
- Stress tests
- Spike tests
- Performance regression testing
- CI/CD pipelines

Unlike Locust, k6 is commonly integrated into automated deployment workflows to ensure performance remains stable across releases.

### Recommended Workflow

```
Development
      │
      ▼
Postman
      │
Verify API Correctness
      │
      ▼
Docker Compose
      │
      ▼
Kubernetes
      │
      ▼
Locust
      │
Generate Realistic Traffic
      │
      ▼
Prometheus / Grafana / Loki / Tempo
      │
      ▼
Observe Platform Behaviour
```

### What We Want to Observe

Using Locust and the platform infrastructure, we can evaluate:

- API response times
- Requests per second
- Error rates
- CPU and memory usage
- Kubernetes autoscaling
- Redis cache hit ratio
- PostgreSQL connection pool usage
- Kafka throughput and consumer lag
- RabbitMQ queue depth
- Distributed traces
- Structured logs
- Prometheus metrics
- Circuit breaker behavior
- Retry logic
- Dead Letter Queue processing

### Tool Usage Summary

| Phase | Tool |
|-------|------|
| API Development | Postman |
| Functional Testing | Postman |
| Local Load Testing | Locust |
| Platform Validation | Locust |
| Performance Regression | k6 |
| Continuous Integration (Optional) | k6 |

### Project Recommendation

For this project:

- **Postman** is used to manually develop and validate APIs.
- **Locust** is the primary traffic generator used to simulate realistic user behavior and exercise the platform.
- **k6** can be added later to automate performance testing as part of the CI/CD pipeline.

This combination provides a practical workflow that reflects how modern platform engineering teams develop, validate, and operate distributed systems.