# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A demo distributed **order-management platform**: three FastAPI microservices
(`order`, `payment`, `notification`) behind an nginx gateway, plus a full local
observability + infra stack, all run via Docker Compose. The point of the repo
is to exercise platform patterns (outbox, circuit breaker, retry, idempotency,
tracing/metrics/logs, DLQ), not the business domain.

## Running the stack

Three compose files, started **in order** (the platform file creates the
external `platform-net` network the others attach to):

```bash
cd platform          && docker compose up -d   # postgres, redis, kafka, rabbitmq, nginx, prometheus, grafana, loki, tempo, otel-collector
cd services          && docker compose up -d   # order-service, payment-service, notification-service
cd traffic-generator && docker compose up -d   # locust (http://localhost:8089)
```

Tear down in reverse order. All service images build with **`context: ..`**
(repo root) so the Dockerfiles can `COPY services/shared`, `services/middleware`,
`services/resilience` alongside the service. After changing a service's
`requirements.txt` or shared code you must rebuild:

```bash
cd services && docker compose build order-service && docker compose up -d order-service
```

Entry points: nginx `:80` routes `/orders`, `/payments`, `/notifications`,
`/health/<svc>`, `/metrics/<svc>`. Grafana `:3000`, Prometheus `:9090`,
RabbitMQ management UI `:15672`, pgadmin `:5050`, Locust `:8089`.

## Tests

```bash
bash test.sh                                              # all three services
cd services/order-service && python -m pytest tests/ -v   # one service
cd services/order-service && python -m pytest tests/test_app.py::TestHealth::test_health_check -v   # one test
```

Tests run **on the host** (Python 3.12+), not in Docker. Each service has a
root `conftest.py` that sets dummy `POSTGRES_*` / `RABBITMQ_*` env (the app
refuses to start without them, see `shared.config.require_env`) and
`DISABLE_BACKGROUND_WORKERS=1` so `TestClient` doesn't spawn broker consumers.
There is no linter or formatter configured.

Alembic migrations exist under each `services/<svc>/alembic/` but **are not run
anywhere** — see "Schema" below.

## Architecture

### Request/event flow (the core thing to understand)

```
POST /orders ──nginx──> order-service
  └─ one DB txn: INSERT orders + INSERT order_outbox        (transactional outbox)
OutboxPoller (daemon thread) ─> Kafka "orders" topic
  └─> payment-service Kafka consumer
        └─ one DB txn: INSERT payments + INSERT payment_outbox
      OutboxPoller ─> RabbitMQ "notifications" queue
        └─> notification-service consumer ─ INSERT notifications
             on failure: nack → dlx exchange → dlq queue → DLQ consumer (logs)
```

Services **never publish inline** — they write an event row to their
`*_outbox` table in the same transaction as the business row, and a background
`OutboxPoller` (`services/shared/outbox.py`) relays it (`FOR UPDATE SKIP LOCKED`,
marks `published_at`). This is why a broker being down never loses an event.

### Per-service layering (all three follow the same shape)

`app/routes/*_router.py` (FastAPI, thin) → `app/service/*_service.py` (business
logic, plain classes, **constructor dependency injection**, depend on ABCs in
`shared/{repository,cache,events,health}.py`) → `app/repository/*_repository.py`
(**raw psycopg2**, not an ORM).

Services are injected only the **swappable** dependencies (repository, cache,
event publisher, health checker) as `shared/*` ABCs. Logging, metrics and
tracing are **ambient** — the service calls `get_logger()` / `get_metric()` /
`get_tracer()` from `shared.observability` directly, not via a constructor
param.

`app/container.py` wires it: `get_container()` returns a **process-wide
singleton** `Container` (one DB pool / broker factory per service). Routers and
the lifespan handler both call `get_container()`.

`app/main.py` owns the FastAPI app, the `lifespan` handler (starts/stops the
daemon threads — outbox poller, Kafka/RabbitMQ consumers — unless
`DISABLE_BACKGROUND_WORKERS=1`), and the `/health` + `/ready` routes (kept in
`main.py`, not routers, for K8s probes).

There is no ORM and no model layer — repositories return plain dicts.

### Shared packages (`services/`, each copied into every image)

`shared/` is organised **by concern** — each module holds its interface *and*
its implementation(s). Import the specific module, never `shared` itself.

| Module | Contents |
|---|---|
| `shared/repository.py` | `Repository` / `OrderRepository` / `PaymentRepository` / `NotificationRepository` ABCs + `OutboxEvent` type. Concrete repos live in each service's `app/repository/`. |
| `shared/cache.py` | `CacheClient` ABC + `RedisCacheClient` |
| `shared/events.py` | `EventPublisher` ABC + `KafkaEventPublisher` + `RabbitMQEventPublisher` |
| `shared/health.py` | `HealthChecker` ABC + `DatabaseHealthChecker` + `RabbitMQHealthChecker` |
| `shared/factories.py` | Connection factories: `create_db_pool`, `create_redis_client`, `create_kafka_producer`, `get_rabbitmq_connection_factory`, `create_circuit_breakers` |
| `shared/outbox.py` | `enqueue_event()` + `OutboxPoller` |
| `shared/config.py` | `require_env`, `get_env` |
| `shared/ratelimit.py` | `setup_rate_limiting(app)` (slowapi limiter + 429 handler + middleware) |
| `shared/observability/` | `logging.py` (`get_logger()` → `StructuredLogger`, JSON to stdout), `metrics.py` (`get_metric()` OTel meter + `setup_metrics_endpoint()`), `tracing.py` (`setup_tracing`, `get_tracer`, `flush_telemetry`, `_resource`). Re-exported from `shared.observability`. |
| `resilience/` | `circuit_breaker.py` (pybreaker instances), `retry.py` (`@default_retry`, tenacity). Deliberately a **separate package**, not merged into `shared/`. |
| `middleware/` | `CorrelationIdMiddleware` (X-Correlation-ID in/out, into `request.state`). Also a separate package by design. |

Rule for the split: an interface + DI only when the thing has multiple real
implementations or is mocked in tests (repo, cache, publisher, health).
Cross-cutting infra with one implementation (logging, metrics, tracing, config)
is a plain module import.

### Schema & config

- **`platform/postgres/init/*.sql` is the source of truth for the DB schema** —
  it runs once on the postgres container's first boot. Alembic is kept in sync
  but not executed. When you change a table, edit the init SQL (and the matching
  Alembic migration for parity).
- **No credential defaults.** `shared.config.require_env` raises at startup if
  `POSTGRES_USER/PASSWORD` or `RABBITMQ_USER/PASS` are missing. They're set in
  `services/docker-compose.yml` and `platform/.env`.
- **RabbitMQ topology** is declared in `platform/rabbitmq/definitions.json`
  (loaded via `load_definitions` in `rabbitmq.conf`). Publishers must **not**
  redeclare the `notifications` queue — it carries `x-dead-letter-exchange` /
  `x-dead-letter-routing-key` args and a mismatched redeclare raises
  `PRECONDITION_FAILED`.

### Observability wiring

- **Traces**: services → OTLP gRPC → `otel-collector` → Tempo.
- **Metrics**: NOT routed through the collector. Each service exposes `/metrics`
  (OTel `PrometheusMetricReader` + `prometheus_client` process stats) and
  Prometheus scrapes each service directly (`platform/prometheus/prometheus.yml`).
- **Logs**: JSON to stdout → promtail (Docker service discovery) → Loki.
- Metric names are **service-specific by convention** (`order_requests_total`,
  not `http_requests_total`).

## Repo scratch (not authoritative)

`docs/scratch/` holds working notes (`tmp*.md`, `zsteps.md`, `shell.md`,
`interface.md`, `services-rule.md`, curl payloads) — historical, not
documentation. `.kilo/worktrees/` holds stale copies — never edit there.
