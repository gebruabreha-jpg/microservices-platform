# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A demo distributed **order-management platform**: three FastAPI microservices
(`order`, `payment`, `notification`) behind an nginx gateway, plus a full local
observability + infra stack, all run via Docker Compose. The point of the repo
is to exercise platform patterns (transactional outbox, circuit breaker, retry,
idempotency, tracing/metrics/logs, DLQ), **not** the business domain.

**Stack:** Python 3.12 · FastAPI · psycopg2 (raw SQL, no ORM) · PostgreSQL ·
Redis · Kafka (`kafka-python`) · RabbitMQ (`pika`) · OpenTelemetry (traces →
Tempo, metrics → Prometheus) · Loki + promtail · pybreaker · tenacity ·
slowapi · pytest · Locust · Docker Compose.

## How the code is organized

```
platform/            infra stack (compose): postgres, redis, kafka, rabbitmq, nginx,
                     prometheus, grafana, loki, tempo, otel-collector, + management UIs
  postgres/init/     *.sql — the actual DB schema (see rules)
  rabbitmq/          definitions.json (topology) + rabbitmq.conf
  prometheus/ grafana/ loki/ otel-collector/ tempo/   observability configs
services/
  <svc>-service/     one per service, all identical shape:
    app/
      main.py        FastAPI app, lifespan (starts/stops background threads), /health + /ready
      container.py   DI wiring — get_container() process-wide singleton
      routes/        thin FastAPI routers
      service/       business logic (plain classes, constructor DI)
      repository/    raw psycopg2, returns plain dicts
      core/database.py  service-specific DB/broker helpers
      schema/        pydantic request/response models
    alembic/         migrations — KEPT IN SYNC, NOT RUN (see rules)
    conftest.py      test env defaults
    tests/
  shared/            organised BY CONCERN — each module = interface + impl(s):
    repository.py    Repository / Order / Payment / Notification ABCs + OutboxEvent type
    cache.py         CacheClient ABC + RedisCacheClient
    events.py        EventPublisher ABC + Kafka / RabbitMQ publishers
    health.py        HealthChecker ABC + Database / RabbitMQ checkers
    factories.py     create_db_pool / create_redis_client / create_kafka_producer /
                     get_rabbitmq_connection_factory / create_circuit_breakers
    outbox.py        enqueue_event() + OutboxPoller
    config.py        require_env / get_env
    ratelimit.py     setup_rate_limiting(app)
    observability/   logging.py (get_logger→StructuredLogger) · metrics.py
                     (get_metric + setup_metrics_endpoint) · tracing.py
                     (setup_tracing / get_tracer / flush_telemetry / _resource)
  resilience/        pybreaker instances + @default_retry — SEPARATE package by design
  middleware/        CorrelationIdMiddleware — SEPARATE package by design
traffic-generator/   Locust load test (locustfile.py, its own compose)
docs/scratch/        historical working notes — not authoritative
```

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

Services **never publish inline** — they write an event row to their `*_outbox`
table in the same transaction as the business row, and a background
`OutboxPoller` (`shared/outbox.py`) relays it (`FOR UPDATE SKIP LOCKED`, marks
`published_at`). A broker being down never loses an event.

`app/container.py`: `get_container()` returns a process-wide singleton
`Container` (one DB pool / broker factory per service). Routers and the lifespan
handler both call it. `app/main.py` owns the FastAPI app + the `lifespan`
handler that starts/stops the daemon threads (outbox poller, Kafka/RabbitMQ
consumers) unless `DISABLE_BACKGROUND_WORKERS=1`.

## Development rules

- **DB schema lives in `platform/postgres/init/*.sql`** (runs once on the
  postgres container's first boot). When you change a table: edit the init SQL
  **and** add the matching Alembic migration for parity. Do not expect Alembic
  to run — it never does.
- **RabbitMQ topology is declared in `platform/rabbitmq/definitions.json`**
  (loaded via `load_definitions`). Never redeclare the `notifications` queue in
  code — it carries `x-dead-letter-exchange` / `x-dead-letter-routing-key` and a
  mismatched redeclare raises `PRECONDITION_FAILED`.
- **`shared/` split rule:** interface + DI only when the thing has multiple real
  implementations or gets mocked in a unit test (repository, cache, publisher,
  health). Cross-cutting infra with one implementation (logging, metrics,
  tracing, config) is a **plain module import** — do not wrap it in an ABC or
  inject it. Do not re-add `Logger` / `MetricsClient` ABCs.
- **No credential defaults.** Read secrets via `shared.config.require_env` (it
  raises at startup if unset). Never add a fallback like `os.getenv("X", "admin")`.
- `middleware/` and `resilience/` stay separate top-level packages — do not
  merge them into `shared/`.
- `/health` and `/ready` routes live in `main.py`, not in routers (K8s probes).
- Metric names are **service-specific** (`order_requests_total`, not
  `http_requests_total`).
- Background workers are started only from the `lifespan` handler and must honour
  the `DISABLE_BACKGROUND_WORKERS` / stop-event contract for clean shutdown.
- `os.environ.setdefault("SERVICE_NAME", ...)` must run **before** importing
  `shared.observability` — the OTel resource is frozen at import.
- Repositories return plain `dict`s. There is no ORM and no model layer.
- Prefer editing one service and mirroring the change to the other two (they are
  deliberately identical in shape). Fix the pattern, not just one instance.
- Do not add a dependency without asking. If you must, pin it consistently with
  the existing `opentelemetry-*` version scheme.

## Workflow

**Before changing code:**
1. Read the canonical service (`order-service`) end to end — `main` → `container`
   → `router` → `service` → `repository`. All three services share this shape.
2. Find the matching test in `services/<svc>/tests/test_app.py`.
3. Match the existing pattern; make the smallest reasonable change.
4. If it's a cross-service concern, apply it to all three + `shared/`.

**After changing code:**
1. `bash test.sh` (or the single service — see Commands).
2. If you touched a `requirements.txt` or anything under `services/shared`,
   `services/middleware`, `services/resilience` → rebuild that service's image.
3. Review the diff. Do not leave unrelated edits in it.
4. Report **what changed and what you verified** (which tests ran, what you
   could not verify — e.g. no live stack).

There is no linter/formatter configured. A full `docker compose up` needs a
running Docker daemon; if it's unavailable, say so rather than claiming the
stack works.

## Commands

```bash
# Run the whole platform — order matters (platform creates the platform-net network)
cd platform          && docker compose up -d
cd services          && docker compose up -d
cd traffic-generator && docker compose up -d          # Locust UI at :8089

# Tear down in reverse order
cd traffic-generator && docker compose down
cd services          && docker compose down
cd platform          && docker compose down

# Rebuild one service after a requirements / shared-code change
cd services && docker compose build order-service && docker compose up -d order-service

# Logs
cd services && docker compose logs -f order-service

# Tests (on the host, Python 3.12+, not in Docker)
bash test.sh                                                               # all three
cd services/order-service && python -m pytest tests/ -v                    # one service
cd services/order-service && python -m pytest tests/test_app.py::TestHealth::test_health_check -v   # one test
```

Entry points once up: nginx `:80` routes `/orders`, `/payments`,
`/notifications`, `/health/<svc>`, `/metrics/<svc>`. Grafana `:3000`,
Prometheus `:9090`, RabbitMQ UI `:15672`, pgadmin `:5050`, Locust `:8089`.

Observability paths: traces → OTLP gRPC → `otel-collector` → Tempo. Metrics →
each service's own `/metrics` scraped directly by Prometheus (no collector hop).
Logs → JSON to stdout → promtail (Docker SD) → Loki.

## Do NOT touch without explicit approval

- **`platform/rabbitmq/definitions.json`** queue/exchange args, or the
  publisher's "don't declare" behaviour — the DLX routing depends on both.
- **Run Alembic against a real database** — `platform/postgres/init/*.sql` owns
  the schema; running migrations on top will collide.
- **`.kilo/worktrees/`** — stale copies, never edit.
- **`platform/.env` and the compose credentials** — the plaintext `admin` /
  `secret` values are intentional for the local demo; don't "secure" them.
- Rewriting working code for style, or refactoring files unrelated to the task
  in hand.
- Upgrading dependencies, unless asked.
- Squashing / rewriting the git history (it's a long `tmp` chain) — ask first.

## Repo scratch (not authoritative)

`docs/scratch/` holds historical working notes (`tmp*.md`, `zsteps.md`,
`shell.md`, `interface.md`, `services-rule.md`, curl payloads).
